"""Modèles de données Pydantic pour les sous-titres."""

from typing import List, Optional
from pathlib import Path
from pydantic import BaseModel, Field, validator
from datetime import timedelta


class SubtitleEntry(BaseModel):
    """Représente une entrée de sous-titre."""
    
    index: int = Field(..., ge=1, description="Index de l'entrée (1-based)")
    start_s: float = Field(..., ge=0, description="Timestamp de début en secondes")
    end_s: float = Field(..., ge=0, description="Timestamp de fin en secondes")
    content: str = Field(..., description="Contenu textuel du sous-titre")
    
    def model_post_init(self, __context) -> None:
        """Validation post-initialisation."""
        if self.end_s <= self.start_s:
            raise ValueError(f"end_s ({self.end_s}) doit être supérieur à start_s ({self.start_s})")
    
    @property
    def duration_s(self) -> float:
        """Durée de l'entrée en secondes."""
        return self.end_s - self.start_s
    
    @property
    def start_timedelta(self) -> timedelta:
        """Timestamp de début en timedelta."""
        return timedelta(seconds=self.start_s)
    
    @property
    def end_timedelta(self) -> timedelta:
        """Timestamp de fin en timedelta."""
        return timedelta(seconds=self.end_s)


class SubtitleFile(BaseModel):
    """Représente un fichier de sous-titres complet."""
    
    file_path: Path = Field(..., description="Chemin du fichier de sous-titres")
    language: Optional[str] = Field(None, description="Code langue (fr, en, etc.)")
    format: str = Field(..., description="Format du fichier (srt, vtt)")
    entries: List[SubtitleEntry] = Field(..., description="Liste des entrées de sous-titres")
    encoding: str = Field(default="utf-8", description="Encodage du fichier")
    
    @property
    def total_duration_s(self) -> float:
        """Durée totale couverte par les sous-titres."""
        if not self.entries:
            return 0.0
        return max(entry.end_s for entry in self.entries)
    
    @property
    def entry_count(self) -> int:
        """Nombre d'entrées de sous-titres."""
        return len(self.entries)


class SubtitleSliceResult(BaseModel):
    """Résultat d'un découpage de sous-titres."""
    
    output_path: Path = Field(..., description="Chemin du fichier de sous-titres généré")
    chapter_index: int = Field(..., ge=1, description="Index du chapitre")
    chapter_title: str = Field(..., description="Titre du chapitre")
    start_s: float = Field(..., ge=0, description="Timestamp de début du chapitre")
    end_s: float = Field(..., ge=0, description="Timestamp de fin du chapitre")
    entry_count: int = Field(..., ge=0, description="Nombre d'entrées dans le fichier généré")
    filtered_count: int = Field(default=0, ge=0, description="Nombre d'entrées filtrées (trop courtes)")
    status: str = Field(..., description="Statut de l'opération (OK, EMPTY, ERROR)")
    message: Optional[str] = Field(None, description="Message d'information ou d'erreur")


