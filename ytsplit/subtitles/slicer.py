"""Découpage de sous-titres par chapitre."""

from pathlib import Path
from typing import List, Optional
from datetime import timedelta

from ..models import Chapter
from ..config import SubtitleSettings
from ..io.naming import generate_safe_filename
from .models import SubtitleEntry, SubtitleFile, SubtitleSliceResult
from .parser import SubtitleParser, create_subtitle_parser


class SubtitleSlicer:
    """Découpe les sous-titres par chapitre."""
    
    def __init__(self, settings: SubtitleSettings, parser: Optional[SubtitleParser] = None):
        self.settings = settings
        self.parser = parser or create_subtitle_parser(encoding=settings.encoding)
    
    def slice_subtitles(
        self,
        subtitle_file: SubtitleFile,
        chapters: List[Chapter],
        output_dir: Path,
        naming_template: str = "{n:02d} - {title}"
    ) -> List[SubtitleSliceResult]:
        """
        Découpe un fichier de sous-titres par chapitre.
        
        Args:
            subtitle_file: Fichier de sous-titres source
            chapters: Liste des chapitres
            output_dir: Répertoire de sortie
            naming_template: Template de nommage des fichiers
            
        Returns:
            Liste des résultats de découpage
        """
        results = []
        
        # Appliquer l'offset global si spécifié
        adjusted_entries = self._apply_offset(subtitle_file.entries, self.settings.offset_s)
        
        # Créer le répertoire de sortie
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for chapter in chapters:
            result = self._slice_chapter(
                adjusted_entries,
                chapter,
                output_dir,
                naming_template
            )
            results.append(result)
        
        return results
    
    def _apply_offset(self, entries: List[SubtitleEntry], offset_s: float) -> List[SubtitleEntry]:
        """Applique un offset temporel aux entrées."""
        if abs(offset_s) < 1e-6:  # Pas d'offset significatif
            return entries
        
        adjusted_entries = []
        for entry in entries:
            new_start = max(0.0, entry.start_s + offset_s)
            new_end = max(new_start + 0.1, entry.end_s + offset_s)  # Durée minimale
            
            adjusted_entries.append(SubtitleEntry(
                index=entry.index,
                start_s=new_start,
                end_s=new_end,
                content=entry.content
            ))
        
        return adjusted_entries
    
    def _slice_chapter(
        self,
        entries: List[SubtitleEntry],
        chapter: Chapter,
        output_dir: Path,
        naming_template: str
    ) -> SubtitleSliceResult:
        """Découpe les sous-titres pour un chapitre spécifique."""
        
        # Générer le nom de fichier
        safe_title = generate_safe_filename(chapter.title)
        filename = naming_template.format(n=chapter.index, title=safe_title)
        output_path = output_dir / f"{filename}.srt"
        
        try:
            # Sélectionner et traiter les sous-titres pour ce chapitre
            chapter_entries = self._extract_chapter_subtitles(entries, chapter)
            
            if not chapter_entries:
                # Créer un fichier vide si aucun sous-titre
                output_path.write_text("", encoding=self.settings.encoding)
                return SubtitleSliceResult(
                    output_path=output_path,
                    chapter_index=chapter.index,
                    chapter_title=chapter.title,
                    start_s=chapter.start_s,
                    end_s=chapter.end_s,
                    entry_count=0,
                    filtered_count=0,
                    status="EMPTY",
                    message="Aucun sous-titre dans ce chapitre"
                )
            
            # Créer le fichier de sous-titres du chapitre
            chapter_subtitle_file = SubtitleFile(
                file_path=output_path,
                language="unknown",  # Sera écrasé par le fichier original
                format="srt",
                entries=chapter_entries,
                encoding=self.settings.encoding
            )
            
            # Écrire le fichier
            self.parser.write_srt_file(chapter_subtitle_file, output_path)
            
            return SubtitleSliceResult(
                output_path=output_path,
                chapter_index=chapter.index,
                chapter_title=chapter.title,
                start_s=chapter.start_s,
                end_s=chapter.end_s,
                entry_count=len(chapter_entries),
                filtered_count=0,  # TODO: Compter les entrées filtrées
                status="OK",
                message=f"Fichier créé avec {len(chapter_entries)} sous-titres"
            )
            
        except Exception as e:
            return SubtitleSliceResult(
                output_path=output_path,
                chapter_index=chapter.index,
                chapter_title=chapter.title,
                start_s=chapter.start_s,
                end_s=chapter.end_s,
                entry_count=0,
                filtered_count=0,
                status="ERROR",
                message=f"Erreur lors de la création: {str(e)}"
            )
    
    def _extract_chapter_subtitles(
        self,
        entries: List[SubtitleEntry],
        chapter: Chapter
    ) -> List[SubtitleEntry]:
        """Extrait et ajuste les sous-titres pour un chapitre."""
        chapter_entries = []
        new_index = 1
        
        chapter_start = chapter.start_s
        chapter_end = chapter.end_s
        
        for entry in entries:
            # Vérifier le chevauchement avec le chapitre
            if entry.end_s <= chapter_start or entry.start_s >= chapter_end:
                continue  # Pas de chevauchement
            
            # Calculer les nouveaux timestamps (tronqués aux bornes du chapitre)
            new_start = max(entry.start_s, chapter_start)
            new_end = min(entry.end_s, chapter_end)
            
            # Rebaser à 0 pour le chapitre
            rebased_start = new_start - chapter_start
            rebased_end = new_end - chapter_start
            
            # Vérifier la durée minimale
            duration_s = rebased_end - rebased_start
            if duration_s < self.settings.min_duration_s:
                # Étendre à la durée minimale si possible
                required_extension = self.settings.min_duration_s - duration_s
                max_end = chapter_end - chapter_start
                
                if rebased_start + self.settings.min_duration_s <= max_end:
                    rebased_end = rebased_start + self.settings.min_duration_s
                else:
                    # Impossible d'étendre suffisamment, ignorer cette entrée
                    continue
            
            # Créer la nouvelle entrée
            chapter_entries.append(SubtitleEntry(
                index=new_index,
                start_s=rebased_start,
                end_s=rebased_end,
                content=entry.content
            ))
            new_index += 1
        
        return chapter_entries
    
    def slice_from_file(
        self,
        subtitle_path: Path,
        chapters: List[Chapter],
        output_dir: Path,
        naming_template: str = "{n:02d} - {title}"
    ) -> List[SubtitleSliceResult]:
        """
        Découpe directement depuis un fichier de sous-titres.
        
        Args:
            subtitle_path: Chemin du fichier de sous-titres source
            chapters: Liste des chapitres
            output_dir: Répertoire de sortie
            naming_template: Template de nommage
            
        Returns:
            Liste des résultats de découpage
        """
        # Parser le fichier
        subtitle_file = self.parser.parse_file(subtitle_path)
        
        # Découper par chapitre
        return self.slice_subtitles(subtitle_file, chapters, output_dir, naming_template)


def create_subtitle_slicer(settings: SubtitleSettings) -> SubtitleSlicer:
    """Factory function pour créer un SubtitleSlicer."""
    return SubtitleSlicer(settings)