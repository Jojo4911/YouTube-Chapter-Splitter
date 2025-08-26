"""Modèles de données Pydantic pour le YouTube Chapter Splitter."""

from typing import Literal, Optional, Union
from pathlib import Path
from pydantic import BaseModel, Field


class Chapter(BaseModel):
    """Représente un chapitre d'une vidéo."""
    
    index: int = Field(..., description="Index du chapitre (1-based)")
    title: str = Field(..., description="Titre du chapitre")
    start_s: float = Field(..., ge=0, description="Timestamp de début en secondes")
    end_s: float = Field(..., ge=0, description="Timestamp de fin en secondes")
    raw_label: Optional[str] = Field(None, description="Libellé brut si parsing description")
    
    def model_post_init(self, __context) -> None:
        """Validation post-initialisation."""
        if self.end_s <= self.start_s:
            raise ValueError(f"end_s ({self.end_s}) doit être supérieur à start_s ({self.start_s})")


class VideoMeta(BaseModel):
    """Métadonnées d'une vidéo YouTube."""
    
    video_id: str = Field(..., description="ID unique de la vidéo YouTube")
    title: str = Field(..., description="Titre de la vidéo")
    duration_s: float = Field(..., gt=0, description="Durée totale en secondes")
    chapters: list[Chapter] = Field(..., description="Liste des chapitres")
    url: str = Field(..., description="URL originale de la vidéo")
    
    def model_post_init(self, __context) -> None:
        """Validation et tri des chapitres."""
        if not self.chapters:
            raise ValueError("Une vidéo doit avoir au moins un chapitre")
        
        # Trier les chapitres par start_s
        self.chapters.sort(key=lambda c: c.start_s)
        
        # Vérifier qu'il n'y a pas de chevauchements
        for i in range(len(self.chapters) - 1):
            if self.chapters[i].end_s > self.chapters[i + 1].start_s:
                raise ValueError(f"Chevauchement détecté entre les chapitres {i+1} et {i+2}")


class SplitPlanItem(BaseModel):
    """Plan de découpage pour un chapitre spécifique."""
    
    video_id: str = Field(..., description="ID de la vidéo source")
    chapter_index: int = Field(..., ge=1, description="Index du chapitre à découper")
    chapter_title: str = Field(..., description="Titre du chapitre")
    start_s: float = Field(..., ge=0, description="Timestamp de début en secondes")
    end_s: float = Field(..., ge=0, description="Timestamp de fin en secondes")
    expected_duration_s: float = Field(..., gt=0, description="Durée attendue en secondes")
    output_path: Path = Field(..., description="Chemin de sortie du fichier")
    mode: Literal["reencode"] = Field(default="reencode", description="Mode de découpage")
    
    def model_post_init(self, __context) -> None:
        """Validation post-initialisation."""
        if self.end_s <= self.start_s:
            raise ValueError(f"end_s ({self.end_s}) doit être supérieur à start_s ({self.start_s})")
        
        calculated_duration = self.end_s - self.start_s
        if abs(calculated_duration - self.expected_duration_s) > 0.001:  # Tolérance pour les erreurs de floating point
            raise ValueError(
                f"expected_duration_s ({self.expected_duration_s}) ne correspond pas au calcul "
                f"end_s - start_s ({calculated_duration})"
            )


class SplitResult(BaseModel):
    """Résultat d'une opération de découpage."""
    
    output_path: Path = Field(..., description="Chemin du fichier généré")
    chapter_index: int = Field(..., ge=1, description="Index du chapitre découpé")
    chapter_title: str = Field(..., description="Titre du chapitre")
    start_s: float = Field(..., ge=0, description="Timestamp de début utilisé")
    end_s: float = Field(..., ge=0, description="Timestamp de fin utilisé")
    expected_duration_s: float = Field(..., gt=0, description="Durée attendue en secondes")
    obtained_duration_s: Optional[float] = Field(None, ge=0, description="Durée réelle du fichier généré")
    status: Literal["OK", "ERR"] = Field(..., description="Statut de l'opération")
    message: Optional[str] = Field(None, description="Message d'erreur ou d'information")
    processing_time_s: Optional[float] = Field(None, ge=0, description="Temps de traitement en secondes")
    
    @property
    def duration_error_s(self) -> Optional[float]:
        """Calcule l'erreur entre la durée attendue et obtenue."""
        if self.obtained_duration_s is None:
            return None
        return abs(self.expected_duration_s - self.obtained_duration_s)
    
    def is_duration_valid(self, tolerance_s: float = 0.15) -> Optional[bool]:
        """Vérifie si la durée est dans la tolérance acceptable."""
        error = self.duration_error_s
        if error is None:
            return None
        return error <= tolerance_s


class ProcessingStats(BaseModel):
    """Statistiques globales d'un traitement."""
    
    total_chapters: int = Field(..., ge=0, description="Nombre total de chapitres")
    successful_chapters: int = Field(..., ge=0, description="Nombre de chapitres traités avec succès")
    failed_chapters: int = Field(..., ge=0, description="Nombre de chapitres en erreur")
    total_duration_s: float = Field(..., ge=0, description="Durée totale traitée en secondes")
    total_processing_time_s: float = Field(..., ge=0, description="Temps total de traitement en secondes")
    
    @property
    def success_rate(self) -> float:
        """Taux de réussite en pourcentage."""
        if self.total_chapters == 0:
            return 0.0
        return (self.successful_chapters / self.total_chapters) * 100.0
    
    def model_post_init(self, __context) -> None:
        """Validation post-initialisation."""
        if self.successful_chapters + self.failed_chapters != self.total_chapters:
            raise ValueError(
                "successful_chapters + failed_chapters doit égaler total_chapters"
            )