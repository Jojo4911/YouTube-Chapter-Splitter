"""Parser pour fichiers de sous-titres SRT/VTT."""

import re
from pathlib import Path
from typing import List, Optional
from datetime import timedelta
import srt

from .models import SubtitleEntry, SubtitleFile


class SubtitleParseError(Exception):
    """Exception levée lors d'erreurs de parsing des sous-titres."""
    pass


class SubtitleParser:
    """Parser pour fichiers de sous-titres."""
    
    def __init__(self, encoding: str = "utf-8"):
        self.encoding = encoding
    
    def parse_file(self, file_path: Path, language: Optional[str] = None) -> SubtitleFile:
        """
        Parse un fichier de sous-titres.
        
        Args:
            file_path: Chemin vers le fichier
            language: Code langue optionnel
            
        Returns:
            SubtitleFile: Fichier parsé
            
        Raises:
            SubtitleParseError: Si le parsing échoue
        """
        if not file_path.exists():
            raise SubtitleParseError(f"Fichier introuvable: {file_path}")
        
        format_type = self._detect_format(file_path)
        
        try:
            content = file_path.read_text(encoding=self.encoding)
        except UnicodeDecodeError as e:
            raise SubtitleParseError(f"Erreur d'encodage lors de la lecture de {file_path}: {e}")
        except Exception as e:
            raise SubtitleParseError(f"Erreur lors de la lecture de {file_path}: {e}")
        
        if format_type == "srt":
            entries = self._parse_srt_content(content)
        elif format_type == "vtt":
            entries = self._parse_vtt_content(content)
        else:
            raise SubtitleParseError(f"Format non supporté: {format_type}")
        
        return SubtitleFile(
            file_path=file_path,
            language=language or self._extract_language_from_filename(file_path),
            format=format_type,
            entries=entries,
            encoding=self.encoding
        )
    
    def _detect_format(self, file_path: Path) -> str:
        """Détecte le format d'un fichier de sous-titres."""
        suffix = file_path.suffix.lower()
        if suffix == ".srt":
            return "srt"
        elif suffix == ".vtt":
            return "vtt"
        else:
            raise SubtitleParseError(f"Extension de fichier non supportée: {suffix}")
    
    def _extract_language_from_filename(self, file_path: Path) -> Optional[str]:
        """Extrait le code langue du nom de fichier."""
        # Format typique: video_id.lang.ext
        name_parts = file_path.stem.split('.')
        if len(name_parts) >= 2:
            potential_lang = name_parts[-1]
            # Codes langue typiques (2-3 caractères)
            if len(potential_lang) in [2, 3] and potential_lang.isalpha():
                return potential_lang.lower()
        return None
    
    def _parse_srt_content(self, content: str) -> List[SubtitleEntry]:
        """Parse le contenu SRT."""
        try:
            srt_entries = list(srt.parse(content))
        except Exception as e:
            raise SubtitleParseError(f"Erreur lors du parsing SRT: {e}")
        
        entries = []
        for srt_entry in srt_entries:
            try:
                start_s = srt_entry.start.total_seconds()
                end_s = srt_entry.end.total_seconds()
                
                # Nettoyer le contenu (supprimer tags HTML/balises)
                clean_content = self._clean_subtitle_content(srt_entry.content)
                
                if clean_content.strip():  # Ignorer les entrées vides
                    entries.append(SubtitleEntry(
                        index=srt_entry.index,
                        start_s=start_s,
                        end_s=end_s,
                        content=clean_content
                    ))
            except Exception as e:
                # Log l'erreur mais continue avec les autres entrées
                print(f"Warning: Erreur lors du parsing de l'entrée SRT {srt_entry.index}: {e}")
                continue
        
        return entries
    
    def _parse_vtt_content(self, content: str) -> List[SubtitleEntry]:
        """Parse le contenu VTT (WebVTT)."""
        # Parser WebVTT basique
        entries = []
        lines = content.split('\n')
        
        i = 0
        entry_index = 1
        
        # Ignorer l'en-tête WebVTT
        while i < len(lines) and not lines[i].strip().startswith('WEBVTT'):
            i += 1
        if i < len(lines):
            i += 1  # Passer la ligne WEBVTT
        
        while i < len(lines):
            line = lines[i].strip()
            i += 1
            
            # Ignorer les lignes vides et commentaires
            if not line or line.startswith('NOTE'):
                continue
            
            # Chercher une ligne de timing (format: 00:00:01.000 --> 00:00:04.000)
            timing_match = re.match(r'(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})', line)
            
            if timing_match:
                start_str = timing_match.group(1).replace(',', '.')
                end_str = timing_match.group(2).replace(',', '.')
                
                try:
                    start_s = self._parse_timestamp(start_str)
                    end_s = self._parse_timestamp(end_str)
                    
                    # Lire le contenu textuel
                    content_lines = []
                    while i < len(lines) and lines[i].strip():
                        content_lines.append(lines[i].strip())
                        i += 1
                    
                    if content_lines:
                        content_text = '\n'.join(content_lines)
                        clean_content = self._clean_subtitle_content(content_text)
                        
                        if clean_content.strip():
                            entries.append(SubtitleEntry(
                                index=entry_index,
                                start_s=start_s,
                                end_s=end_s,
                                content=clean_content
                            ))
                            entry_index += 1
                            
                except Exception as e:
                    print(f"Warning: Erreur lors du parsing de l'entrée VTT: {e}")
                    continue
        
        return entries
    
    def _parse_timestamp(self, timestamp_str: str) -> float:
        """Parse un timestamp au format HH:MM:SS.mmm."""
        try:
            # Remplacer les virgules par des points pour les millisecondes
            timestamp_str = timestamp_str.replace(',', '.')
            
            # Parser le format HH:MM:SS.mmm
            parts = timestamp_str.split(':')
            if len(parts) != 3:
                raise ValueError(f"Format timestamp invalide: {timestamp_str}")
            
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds_parts = parts[2].split('.')
            seconds = int(seconds_parts[0])
            
            # Gérer les millisecondes
            milliseconds = 0
            if len(seconds_parts) > 1:
                # Normaliser à 3 chiffres
                ms_str = seconds_parts[1][:3].ljust(3, '0')
                milliseconds = int(ms_str)
            
            total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0
            return total_seconds
            
        except (ValueError, IndexError) as e:
            raise SubtitleParseError(f"Erreur lors du parsing du timestamp '{timestamp_str}': {e}")
    
    def _clean_subtitle_content(self, content: str) -> str:
        """Nettoie le contenu des sous-titres."""
        if not content:
            return ""
        
        # Supprimer les balises HTML basiques
        content = re.sub(r'<[^>]*>', '', content)
        
        # Supprimer les balises WebVTT
        content = re.sub(r'<c[^>]*>(.*?)</c>', r'\1', content)
        content = re.sub(r'<v[^>]*>(.*?)</v>', r'\1', content)
        
        # Normaliser les espaces
        content = re.sub(r'\s+', ' ', content)
        
        return content.strip()
    
    def write_srt_file(self, subtitle_file: SubtitleFile, output_path: Path) -> None:
        """
        Écrit un fichier SRT.
        
        Args:
            subtitle_file: Fichier de sous-titres à écrire
            output_path: Chemin de sortie
        """
        try:
            # Créer les objets srt.Subtitle
            srt_subtitles = []
            for entry in subtitle_file.entries:
                srt_subtitle = srt.Subtitle(
                    index=entry.index,
                    start=timedelta(seconds=entry.start_s),
                    end=timedelta(seconds=entry.end_s),
                    content=entry.content
                )
                srt_subtitles.append(srt_subtitle)
            
            # Générer le contenu SRT
            srt_content = srt.compose(srt_subtitles)
            
            # Écrire le fichier
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(srt_content, encoding=subtitle_file.encoding)
            
        except Exception as e:
            raise SubtitleParseError(f"Erreur lors de l'écriture du fichier SRT {output_path}: {e}")


def create_subtitle_parser(encoding: str = "utf-8") -> SubtitleParser:
    """Factory function pour créer un SubtitleParser."""
    return SubtitleParser(encoding=encoding)