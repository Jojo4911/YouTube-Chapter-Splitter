"""Module d'intégration avec yt-dlp pour YouTube."""

import subprocess
import json
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs

from ..models import VideoMeta, Chapter
from ..config import Settings


class YouTubeError(Exception):
    """Exception levée lors d'erreurs liées à YouTube."""
    pass


class YouTubeProvider:
    """Provider pour l'interaction avec YouTube via yt-dlp."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._validate_ytdlp()
    
    def _validate_ytdlp(self) -> None:
        """Vérifie que yt-dlp est disponible."""
        try:
            result = subprocess.run(
                ["yt-dlp", "--version"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            if result.returncode != 0:
                raise YouTubeError("yt-dlp n'est pas correctement installé")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            raise YouTubeError(f"yt-dlp n'est pas disponible: {e}")
    
    def validate_youtube_url(self, url: str) -> bool:
        """Valide qu'une URL est bien une URL YouTube valide."""
        try:
            parsed = urlparse(url)
            
            # Domaines YouTube supportés
            valid_domains = [
                'youtube.com', 'www.youtube.com',
                'youtu.be', 'www.youtu.be',
                'm.youtube.com'
            ]
            
            if parsed.netloc not in valid_domains:
                return False
            
            # Vérifier la présence d'un ID vidéo
            if parsed.netloc == 'youtu.be':
                # Format: https://youtu.be/VIDEO_ID
                return len(parsed.path.lstrip('/')) == 11
            else:
                # Format: https://youtube.com/watch?v=VIDEO_ID
                query_params = parse_qs(parsed.query)
                video_id = query_params.get('v', [])
                return len(video_id) == 1 and len(video_id[0]) == 11
                
        except Exception:
            return False
    
    def extract_video_id(self, url: str) -> str:
        """Extrait l'ID vidéo d'une URL YouTube."""
        if not self.validate_youtube_url(url):
            raise YouTubeError(f"URL YouTube invalide: {url}")
        
        parsed = urlparse(url)
        
        if parsed.netloc == 'youtu.be':
            return parsed.path.lstrip('/')
        else:
            query_params = parse_qs(parsed.query)
            return query_params['v'][0]
    
    def get_video_info(self, url: str) -> VideoMeta:
        """
        Récupère les métadonnées d'une vidéo YouTube.
        
        Args:
            url: URL de la vidéo YouTube
            
        Returns:
            VideoMeta: Métadonnées complètes de la vidéo
            
        Raises:
            YouTubeError: Si l'extraction échoue
        """
        if not self.validate_youtube_url(url):
            raise YouTubeError(f"URL YouTube invalide: {url}")
        
        try:
            # Commande yt-dlp pour extraire les métadonnées JSON
            cmd = [
                "yt-dlp",
                "--dump-json",
                "--no-download",
                "--no-warnings",
                url
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                raise YouTubeError(f"Échec de l'extraction des métadonnées: {result.stderr}")
            
            # Parser le JSON
            try:
                info = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                raise YouTubeError(f"Réponse JSON invalide de yt-dlp: {e}")
            
            # Convertir en VideoMeta
            return self._convert_ytdlp_info_to_meta(info, url)
            
        except subprocess.TimeoutExpired:
            raise YouTubeError("Timeout lors de l'extraction des métadonnées")
        except Exception as e:
            raise YouTubeError(f"Erreur inattendue lors de l'extraction: {e}")
    
    def _convert_ytdlp_info_to_meta(self, info: Dict[str, Any], original_url: str) -> VideoMeta:
        """Convertit les métadonnées yt-dlp en VideoMeta."""
        video_id = info.get('id', '')
        title = info.get('title', 'Titre inconnu')
        duration = info.get('duration', 0)
        
        if not video_id:
            raise YouTubeError("ID vidéo manquant dans les métadonnées")
        
        if duration <= 0:
            raise YouTubeError("Durée vidéo invalide")
        
        # Extraire les chapitres
        chapters = self._extract_chapters_from_info(info)
        
        # Si pas de chapitres structurés, créer un chapitre unique
        if not chapters:
            chapters = [Chapter(
                index=1,
                title=title,
                start_s=0.0,
                end_s=float(duration),
                raw_label=None
            )]
        
        return VideoMeta(
            video_id=video_id,
            title=title,
            duration_s=float(duration),
            chapters=chapters,
            url=original_url
        )
    
    def _extract_chapters_from_info(self, info: Dict[str, Any]) -> List[Chapter]:
        """Extrait les chapitres depuis les métadonnées yt-dlp."""
        chapters = []
        ytdlp_chapters = info.get('chapters', [])
        
        if not ytdlp_chapters:
            return chapters
        
        for i, chapter_info in enumerate(ytdlp_chapters, 1):
            start_time = chapter_info.get('start_time', 0)
            end_time = chapter_info.get('end_time', start_time)
            title = chapter_info.get('title', f'Chapitre {i}')
            
            # Validation basique
            if end_time <= start_time:
                continue
            
            chapters.append(Chapter(
                index=i,
                title=title,
                start_s=float(start_time),
                end_s=float(end_time),
                raw_label=None
            ))
        
        return chapters
    
    def download_video(self, url: str, output_dir: Optional[Path] = None) -> Path:
        """
        Télécharge une vidéo YouTube.
        
        Args:
            url: URL de la vidéo
            output_dir: Répertoire de sortie (utilise work_dir si None)
            
        Returns:
            Path: Chemin du fichier téléchargé
            
        Raises:
            YouTubeError: Si le téléchargement échoue
        """
        if not self.validate_youtube_url(url):
            raise YouTubeError(f"URL YouTube invalide: {url}")
        
        if output_dir is None:
            output_dir = self.settings.work_dir
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Générer un nom de fichier basé sur l'ID vidéo
        video_id = self.extract_video_id(url)
        output_template = output_dir / f"{video_id}.%(ext)s"
        
        try:
            cmd = [
                "yt-dlp",
                "--format", self.settings.yt_dlp_format,
                "--output", str(output_template),
                "--merge-output-format", self.settings.video_format,
                "--no-warnings",
                url
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1800  # 30 minutes max
            )
            
            if result.returncode != 0:
                raise YouTubeError(f"Échec du téléchargement: {result.stderr}")
            
            # Trouver le fichier téléchargé
            expected_file = output_dir / f"{video_id}.{self.settings.video_format}"
            
            if not expected_file.exists():
                # Chercher des fichiers avec le même préfixe
                matching_files = list(output_dir.glob(f"{video_id}.*"))
                if matching_files:
                    expected_file = matching_files[0]
                else:
                    raise YouTubeError(f"Fichier téléchargé introuvable: {expected_file}")
            
            return expected_file
            
        except subprocess.TimeoutExpired:
            raise YouTubeError("Timeout lors du téléchargement (>30min)")
        except Exception as e:
            raise YouTubeError(f"Erreur inattendue lors du téléchargement: {e}")
    
    def get_video_file_path(self, video_id: str, output_dir: Optional[Path] = None) -> Optional[Path]:
        """
        Vérifie si une vidéo est déjà téléchargée.
        
        Args:
            video_id: ID de la vidéo YouTube
            output_dir: Répertoire où chercher
            
        Returns:
            Path: Chemin du fichier s'il existe, None sinon
        """
        if output_dir is None:
            output_dir = self.settings.work_dir
        
        # Chercher des fichiers avec l'ID vidéo
        for ext in ['mp4', 'mkv', 'webm', 'avi']:
            file_path = output_dir / f"{video_id}.{ext}"
            if file_path.exists() and file_path.stat().st_size > 0:
                return file_path
        
        return None
    
    def process_video(self, url: str, force_redownload: bool = False) -> tuple[VideoMeta, Path]:
        """
        Traite une vidéo complètement : métadonnées + téléchargement.
        
        Args:
            url: URL YouTube
            force_redownload: Force le retéléchargement même si le fichier existe
            
        Returns:
            tuple: (VideoMeta, Path du fichier)
        """
        # Extraction des métadonnées
        meta = self.get_video_info(url)
        
        # Vérifier si déjà téléchargée
        existing_file = self.get_video_file_path(meta.video_id)
        
        if existing_file and not force_redownload:
            return meta, existing_file
        
        # Télécharger
        video_file = self.download_video(url)
        
        return meta, video_file


def create_youtube_provider(settings: Optional[Settings] = None) -> YouTubeProvider:
    """Factory function pour créer un YouTubeProvider."""
    if settings is None:
        from ..config import get_default_settings
        settings = get_default_settings()
    
    return YouTubeProvider(settings)