"""Module de découpage vidéo avec FFmpeg."""

import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, Any

from ..models import SplitPlanItem, SplitResult
from ..config import Settings
from ..parsing.timecode import seconds_to_timecode


class FFmpegError(Exception):
    """Exception levée lors d'erreurs FFmpeg."""
    pass


class FFmpegCutter:
    """Découpage vidéo précis avec FFmpeg."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._validate_ffmpeg()
    
    def _validate_ffmpeg(self) -> None:
        """Vérifie que FFmpeg est disponible."""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise FFmpegError("FFmpeg n'est pas correctement installé")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            raise FFmpegError(f"FFmpeg n'est pas disponible: {e}")
    
    def cut_precise(
        self,
        source_path: Path,
        plan_item: SplitPlanItem,
        retry_count: int = 0
    ) -> SplitResult:
        """
        Découpe précise d'un segment vidéo avec ré-encodage.
        
        Args:
            source_path: Chemin du fichier vidéo source
            plan_item: Plan de découpage du segment
            retry_count: Nombre de tentatives (pour retry automatique)
            
        Returns:
            SplitResult: Résultat du découpage
        """
        start_time = time.time()
        
        try:
            # Validation des inputs
            if not source_path.exists():
                raise FFmpegError(f"Fichier source introuvable: {source_path}")
            
            # Créer le répertoire de sortie si nécessaire
            plan_item.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Construire la commande FFmpeg
            cmd = self._build_ffmpeg_command(source_path, plan_item)
            
            # Exécuter FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes max par segment
            )
            
            processing_time = time.time() - start_time
            
            if result.returncode != 0:
                error_msg = f"FFmpeg a échoué (code {result.returncode})"
                if result.stderr:
                    error_msg += f": {result.stderr.strip()}"
                
                # Retry automatique avec preset plus lent si c'est la première tentative
                if retry_count == 0 and self.settings.validation.max_retries > 0:
                    return self._retry_with_slower_preset(source_path, plan_item)
                
                return SplitResult(
                    output_path=plan_item.output_path,
                    chapter_index=plan_item.chapter_index,
                    chapter_title=plan_item.chapter_title,
                    start_s=plan_item.start_s,
                    end_s=plan_item.end_s,
                    expected_duration_s=plan_item.expected_duration_s,
                    obtained_duration_s=None,
                    status="ERR",
                    message=error_msg,
                    processing_time_s=processing_time
                )
            
            # Vérifier que le fichier de sortie existe
            if not plan_item.output_path.exists():
                return SplitResult(
                    output_path=plan_item.output_path,
                    chapter_index=plan_item.chapter_index,
                    chapter_title=plan_item.chapter_title,
                    start_s=plan_item.start_s,
                    end_s=plan_item.end_s,
                    expected_duration_s=plan_item.expected_duration_s,
                    obtained_duration_s=None,
                    status="ERR",
                    message="Fichier de sortie non créé",
                    processing_time_s=processing_time
                )
            
            # Valider la durée du fichier de sortie
            from ..utils.ffprobe import get_video_duration
            obtained_duration = get_video_duration(plan_item.output_path)
            
            # Vérifier la tolérance
            duration_error = abs(plan_item.expected_duration_s - obtained_duration)
            is_valid = duration_error <= self.settings.validation.tolerance_seconds
            
            return SplitResult(
                output_path=plan_item.output_path,
                chapter_index=plan_item.chapter_index,
                chapter_title=plan_item.chapter_title,
                start_s=plan_item.start_s,
                end_s=plan_item.end_s,
                expected_duration_s=plan_item.expected_duration_s,
                obtained_duration_s=obtained_duration,
                status="OK" if is_valid else "ERR",
                message=f"Erreur de durée: {duration_error:.2f}s" if not is_valid else None,
                processing_time_s=processing_time
            )
            
        except subprocess.TimeoutExpired:
            processing_time = time.time() - start_time
            return SplitResult(
                output_path=plan_item.output_path,
                chapter_index=plan_item.chapter_index,
                chapter_title=plan_item.chapter_title,
                start_s=plan_item.start_s,
                end_s=plan_item.end_s,
                expected_duration_s=plan_item.expected_duration_s,
                obtained_duration_s=None,
                status="ERR",
                message="Timeout FFmpeg (>5min)",
                processing_time_s=processing_time
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            return SplitResult(
                output_path=plan_item.output_path,
                chapter_index=plan_item.chapter_index,
                chapter_title=plan_item.chapter_title,
                start_s=plan_item.start_s,
                end_s=plan_item.end_s,
                expected_duration_s=plan_item.expected_duration_s,
                obtained_duration_s=None,
                status="ERR",
                message=f"Erreur inattendue: {str(e)}",
                processing_time_s=processing_time
            )
    
    def _retry_with_slower_preset(
        self,
        source_path: Path,
        plan_item: SplitPlanItem
    ) -> SplitResult:
        """Retry avec un preset plus lent pour plus de précision."""
        # Sauvegarder le preset original
        original_preset = self.settings.x264.preset
        
        # Mapper vers un preset plus lent
        slower_presets = {
            "ultrafast": "veryfast",
            "superfast": "veryfast", 
            "veryfast": "faster",
            "faster": "fast",
            "fast": "medium",
            "medium": "slow",
            "slow": "slower",
            "slower": "veryslow"
        }
        
        new_preset = slower_presets.get(original_preset, "medium")
        self.settings.x264.preset = new_preset
        
        try:
            result = self.cut_precise(source_path, plan_item, retry_count=1)
            # Ajouter une note sur le retry
            if result.status == "OK":
                result.message = f"Réussi avec preset {new_preset} (retry)"
            return result
        finally:
            # Restaurer le preset original
            self.settings.x264.preset = original_preset
    
    def _build_ffmpeg_command(self, source_path: Path, plan_item: SplitPlanItem) -> list[str]:
        """Construit la commande FFmpeg pour le découpage précis."""
        
        # Convertir les timestamps en format HH:MM:SS.mmm
        start_time = seconds_to_timecode(plan_item.start_s, include_milliseconds=True)
        end_time = seconds_to_timecode(plan_item.end_s, include_milliseconds=True)
        
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-i", str(source_path),
            "-ss", start_time,
            "-to", end_time,
        ]
        
        # Ajouter le filtre crop si activé
        if self.settings.crop.enabled:
            crop_filter = self._build_crop_filter(source_path)
            if crop_filter:
                cmd.extend(["-vf", crop_filter])
        
        cmd.extend([
            "-c:v", "libx264",
            "-crf", str(self.settings.x264.crf),
            "-preset", self.settings.x264.preset,
            "-c:a", self.settings.audio.codec,
            "-b:a", self.settings.audio.bitrate,
            "-movflags", "+faststart",
            "-map", "0",
            "-y",  # Overwrite output files
            str(plan_item.output_path)
        ])
        
        return cmd
    
    def _build_crop_filter(self, source_path: Path) -> Optional[str]:
        """
        Construit le filtre crop FFmpeg basé sur la configuration.
        
        Args:
            source_path: Chemin du fichier source pour obtenir la résolution
            
        Returns:
            str: Filtre crop au format "crop=width:height:x:y" ou None si invalid
        """
        try:
            # Obtenir la résolution de la vidéo source
            from ..utils.ffprobe import get_video_resolution
            source_width, source_height = get_video_resolution(source_path)
            
            # Calculer les dimensions après crop
            crop_width = source_width - self.settings.crop.left - self.settings.crop.right
            crop_height = source_height - self.settings.crop.top - self.settings.crop.bottom
            
            # Validation des dimensions minimales
            if crop_width < self.settings.crop.min_width:
                raise ValueError(f"Largeur après crop ({crop_width}px) < minimum ({self.settings.crop.min_width}px)")
            
            if crop_height < self.settings.crop.min_height:
                raise ValueError(f"Hauteur après crop ({crop_height}px) < minimum ({self.settings.crop.min_height}px)")
            
            # Si pas de crop nécessaire (tous les paramètres sont 0)
            if all(getattr(self.settings.crop, side) == 0 for side in ['top', 'bottom', 'left', 'right']):
                return None
            
            # Format FFmpeg: crop=width:height:x:y
            # x = position horizontale (left offset)
            # y = position verticale (top offset)
            return f"crop={crop_width}:{crop_height}:{self.settings.crop.left}:{self.settings.crop.top}"
            
        except Exception as e:
            # En cas d'erreur, on log et on désactive le crop
            print(f"Erreur lors de la construction du filtre crop: {e}")
            return None
    
    def cut_batch(
        self,
        source_path: Path,
        plan_items: list[SplitPlanItem],
        progress_callback: Optional[callable] = None
    ) -> list[SplitResult]:
        """
        Découpe plusieurs segments en lot.
        
        Args:
            source_path: Chemin du fichier source
            plan_items: Liste des plans de découpage
            progress_callback: Callback pour le suivi de progression (optionnel)
            
        Returns:
            list[SplitResult]: Résultats de tous les découpages
        """
        results = []
        total_items = len(plan_items)
        
        for i, plan_item in enumerate(plan_items):
            # Callback de progression
            if progress_callback:
                progress_callback(i, total_items, plan_item.chapter_title)
            
            # Vérifier si le fichier existe déjà et est valide
            if (plan_item.output_path.exists() and 
                self.settings.skip_existing and 
                self._is_output_valid(plan_item)):
                
                # Créer un résultat "skipped" 
                from ..utils.ffprobe import get_video_duration
                obtained_duration = get_video_duration(plan_item.output_path)
                
                result = SplitResult(
                    output_path=plan_item.output_path,
                    chapter_index=plan_item.chapter_index,
                    chapter_title=plan_item.chapter_title,
                    start_s=plan_item.start_s,
                    end_s=plan_item.end_s,
                    expected_duration_s=plan_item.expected_duration_s,
                    obtained_duration_s=obtained_duration,
                    status="OK",
                    message="Fichier existant (skipped)",
                    processing_time_s=0.0
                )
            else:
                # Découper le segment
                result = self.cut_precise(source_path, plan_item)
            
            results.append(result)
        
        return results
    
    def _is_output_valid(self, plan_item: SplitPlanItem) -> bool:
        """Vérifie si un fichier de sortie existant est valide."""
        try:
            if not plan_item.output_path.exists():
                return False
            
            # Vérifier que le fichier n'est pas vide
            if plan_item.output_path.stat().st_size == 0:
                return False
            
            # Vérifier la durée si possible
            from ..utils.ffprobe import get_video_duration
            obtained_duration = get_video_duration(plan_item.output_path)
            duration_error = abs(plan_item.expected_duration_s - obtained_duration)
            
            return duration_error <= self.settings.validation.tolerance_seconds
            
        except Exception:
            return False


def create_ffmpeg_cutter(settings: Optional[Settings] = None) -> FFmpegCutter:
    """Factory function pour créer un FFmpegCutter."""
    if settings is None:
        from ..config import get_default_settings
        settings = get_default_settings()
    
    return FFmpegCutter(settings)