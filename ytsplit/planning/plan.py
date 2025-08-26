"""Module de planification des segments de découpage."""

from pathlib import Path
from typing import List, Optional

from ..models import VideoMeta, Chapter, SplitPlanItem
from ..config import Settings
from ..io.naming import generate_safe_filename


class PlanningError(Exception):
    """Exception levée lors d'erreurs de planification."""
    pass


class SplitPlanner:
    """Planificateur de découpage de vidéos en segments."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
    
    def build_split_plan(self, meta: VideoMeta, output_dir: Optional[Path] = None) -> List[SplitPlanItem]:
        """
        Construit un plan de découpage complet pour une vidéo.
        
        Args:
            meta: Métadonnées de la vidéo avec chapitres
            output_dir: Répertoire de sortie (utilise settings.out_dir si None)
            
        Returns:
            List[SplitPlanItem]: Plan de découpage complet
            
        Raises:
            PlanningError: Si la planification échoue
        """
        if not meta.chapters:
            raise PlanningError("Aucun chapitre à planifier")
        
        if output_dir is None:
            output_dir = self.settings.out_dir
        
        # Créer le répertoire spécifique à la vidéo
        video_output_dir = output_dir / self._sanitize_video_title(meta.title, meta.video_id)
        
        plan_items = []
        
        for chapter in meta.chapters:
            # Générer le nom de fichier de sortie
            filename = self._generate_chapter_filename(chapter)
            output_path = video_output_dir / filename
            
            # Calculer la durée attendue
            expected_duration = chapter.end_s - chapter.start_s
            
            if expected_duration <= 0:
                raise PlanningError(
                    f"Durée invalide pour le chapitre {chapter.index}: "
                    f"{expected_duration:.2f}s (start: {chapter.start_s}s, end: {chapter.end_s}s)"
                )
            
            # Créer l'item de planification
            plan_item = SplitPlanItem(
                video_id=meta.video_id,
                chapter_index=chapter.index,
                chapter_title=chapter.title,
                start_s=chapter.start_s,
                end_s=chapter.end_s,
                expected_duration_s=expected_duration,
                output_path=output_path,
                mode="reencode"  # Mode précis par défaut selon les spécifications
            )
            
            plan_items.append(plan_item)
        
        # Validation du plan complet
        self._validate_plan(plan_items, meta.duration_s)
        
        return plan_items
    
    def _sanitize_video_title(self, title: str, video_id: str) -> str:
        """
        Crée un nom de répertoire sûr pour la vidéo.
        
        Args:
            title: Titre de la vidéo
            video_id: ID de la vidéo (fallback)
            
        Returns:
            str: Nom de répertoire sanitisé
        """
        # Utiliser le système de nommage sûr
        safe_title = generate_safe_filename(
            title,
            max_length=50,  # Plus court pour les répertoires
            replace_chars=self.settings.naming.replace_chars
        )
        
        # Ajouter l'ID vidéo pour l'unicité
        return f"{safe_title}-{video_id}"
    
    def _generate_chapter_filename(self, chapter: Chapter) -> str:
        """
        Génère un nom de fichier sûr pour un chapitre.
        
        Args:
            chapter: Chapitre à nommer
            
        Returns:
            str: Nom de fichier avec extension
        """
        # Utiliser le template de nommage depuis la configuration
        template = self.settings.naming.template
        
        # Variables disponibles pour le template
        variables = {
            "n": chapter.index,
            "title": chapter.title,
            "start": int(chapter.start_s),
            "end": int(chapter.end_s),
            "duration": int(chapter.end_s - chapter.start_s)
        }
        
        # Appliquer le template
        filename = template.format(**variables)
        
        # Sanitiser le nom de fichier
        safe_filename = generate_safe_filename(
            filename,
            max_length=self.settings.naming.sanitize_maxlen,
            replace_chars=self.settings.naming.replace_chars
        )
        
        # Ajouter l'extension
        return f"{safe_filename}.{self.settings.video_format}"
    
    def _validate_plan(self, plan_items: List[SplitPlanItem], video_duration: float) -> None:
        """
        Valide la cohérence d'un plan de découpage.
        
        Args:
            plan_items: Items du plan à valider
            video_duration: Durée totale de la vidéo
            
        Raises:
            PlanningError: Si le plan est incohérent
        """
        if not plan_items:
            raise PlanningError("Plan vide")
        
        # Vérifier que tous les segments sont dans les limites de la vidéo
        for item in plan_items:
            if item.start_s < 0:
                raise PlanningError(
                    f"Chapitre {item.chapter_index}: start_s négatif ({item.start_s}s)"
                )
            
            if item.end_s > video_duration + 1.0:  # Tolérance de 1 seconde
                raise PlanningError(
                    f"Chapitre {item.chapter_index}: end_s ({item.end_s}s) dépasse la durée vidéo ({video_duration}s)"
                )
            
            if item.expected_duration_s <= 0:
                raise PlanningError(
                    f"Chapitre {item.chapter_index}: durée nulle ou négative ({item.expected_duration_s}s)"
                )
        
        # Vérifier l'ordre chronologique
        sorted_items = sorted(plan_items, key=lambda x: x.start_s)
        for i in range(len(sorted_items) - 1):
            current = sorted_items[i]
            next_item = sorted_items[i + 1]
            
            if current.end_s > next_item.start_s:
                raise PlanningError(
                    f"Chevauchement détecté entre chapitres {current.chapter_index} et {next_item.chapter_index}"
                )
        
        # Vérifier l'unicité des noms de fichiers de sortie
        output_paths = [item.output_path for item in plan_items]
        unique_paths = set(output_paths)
        
        if len(unique_paths) != len(output_paths):
            duplicates = []
            seen = set()
            for path in output_paths:
                if path in seen:
                    duplicates.append(path.name)
                seen.add(path)
            
            raise PlanningError(f"Noms de fichiers en doublon: {', '.join(duplicates)}")
    
    def filter_existing_files(self, plan_items: List[SplitPlanItem]) -> tuple[List[SplitPlanItem], List[SplitPlanItem]]:
        """
        Sépare les éléments du plan en fichiers à traiter et fichiers existants.
        
        Args:
            plan_items: Plan complet
            
        Returns:
            tuple: (items_to_process, existing_items)
        """
        items_to_process = []
        existing_items = []
        
        for item in plan_items:
            if item.output_path.exists() and self.settings.skip_existing:
                # Vérifier que le fichier existant est valide
                try:
                    from ..utils.ffprobe import get_video_duration
                    existing_duration = get_video_duration(item.output_path)
                    duration_error = abs(item.expected_duration_s - existing_duration)
                    
                    if duration_error <= self.settings.validation.tolerance_seconds:
                        existing_items.append(item)
                        continue
                except Exception:
                    pass  # Si on ne peut pas valider, on retraite le fichier
            
            items_to_process.append(item)
        
        return items_to_process, existing_items
    
    def estimate_processing_time(self, plan_items: List[SplitPlanItem]) -> dict:
        """
        Estime le temps de traitement pour un plan.
        
        Args:
            plan_items: Plan de découpage
            
        Returns:
            dict: Estimations de temps
        """
        total_duration = sum(item.expected_duration_s for item in plan_items)
        
        # Estimation basée sur des heuristiques
        # Le ré-encodage prend généralement 0.5x à 2x la durée de la vidéo
        # selon la complexité et le preset
        preset_multipliers = {
            "ultrafast": 0.3,
            "superfast": 0.4,
            "veryfast": 0.5,
            "faster": 0.8,
            "fast": 1.0,
            "medium": 1.5,
            "slow": 2.0,
            "slower": 3.0,
            "veryslow": 5.0
        }
        
        multiplier = preset_multipliers.get(self.settings.x264.preset, 1.0)
        
        # Estimation du temps de traitement
        estimated_seconds = total_duration * multiplier
        
        # Ajuster selon le nombre de workers parallèles
        if self.settings.parallel.max_workers > 1:
            estimated_seconds = estimated_seconds / min(self.settings.parallel.max_workers, len(plan_items))
        
        return {
            "total_video_duration": total_duration,
            "estimated_processing_time": estimated_seconds,
            "preset_used": self.settings.x264.preset,
            "parallel_workers": min(self.settings.parallel.max_workers, len(plan_items)),
            "chapters_count": len(plan_items)
        }


def create_split_planner(settings: Optional[Settings] = None) -> SplitPlanner:
    """Factory function pour créer un SplitPlanner."""
    if settings is None:
        from ..config import get_default_settings
        settings = get_default_settings()
    
    return SplitPlanner(settings)