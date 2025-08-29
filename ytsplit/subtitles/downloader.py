"""Téléchargeur de sous-titres avec intégration YouTube et recherche locale."""

from pathlib import Path
from typing import Optional, List

from ..providers.youtube import YouTubeProvider, YouTubeError
from ..config import SubtitleSettings
from .models import SubtitleFile
from .parser import SubtitleParser, create_subtitle_parser


class SubtitleDownloadError(Exception):
    """Exception levée lors d'erreurs de téléchargement de sous-titres."""
    pass


class SubtitleDownloader:
    """Téléchargeur et gestionnaire de sous-titres."""

    def __init__(self, settings: SubtitleSettings, youtube_provider: Optional[YouTubeProvider] = None):
        self.settings = settings
        self.youtube_provider = youtube_provider
        self.parser = create_subtitle_parser(encoding=settings.encoding)

    def get_subtitle_file(self, url: str, video_id: str, work_dir: Path) -> Optional[SubtitleFile]:
        """Récupère un fichier de sous-titres (externe, local, ou téléchargement auto)."""
        # 1) Fichier externe fourni explicitement
        if self.settings.external_srt_path:
            try:
                return self.parser.parse_file(self.settings.external_srt_path)
            except Exception as e:
                raise SubtitleDownloadError(
                    f"Erreur lors du parsing du fichier externe {self.settings.external_srt_path}: {e}"
                )

        # 2) Recherche locale (work_dir + répertoires personnalisés)
        local = self._find_local_subtitle_file(video_id, work_dir)
        if local is not None:
            return local

        # 3) Téléchargement automatique (si activé et provider présent)
        if self.settings.auto_download and self.youtube_provider:
            try:
                return self._download_from_youtube(url, video_id, work_dir)
            except SubtitleDownloadError:
                return None

        return None

    def _download_from_youtube(self, url: str, video_id: str, work_dir: Path) -> Optional[SubtitleFile]:
        """Télécharge les sous-titres depuis YouTube via yt-dlp provider."""
        if not self.youtube_provider:
            raise SubtitleDownloadError("Provider YouTube non configuré")

        try:
            # Vérifier si déjà téléchargé (sauf si force_redownload)
            if not self.settings.force_redownload:
                if hasattr(self.youtube_provider, 'get_subtitles_file_path'):
                    existing_path = self.youtube_provider.get_subtitles_file_path(video_id, work_dir)
                    if existing_path:
                        return self.parser.parse_file(existing_path)

            subtitle_path = self.youtube_provider.download_subtitles(
                url=url,
                languages=self.settings.languages,
                format_priority=self.settings.format_priority,
                output_dir=work_dir
            )

            if not subtitle_path:
                return None

            return self.parser.parse_file(subtitle_path)

        except YouTubeError as e:
            raise SubtitleDownloadError(f"Erreur YouTube lors du téléchargement: {e}")
        except Exception as e:
            raise SubtitleDownloadError(f"Erreur inattendue lors du téléchargement: {e}")

    def _find_local_subtitle_file(self, video_id: str, work_dir: Path) -> Optional[SubtitleFile]:
        """Cherche un fichier SRT/VTT local par video_id dans work_dir puis dans settings.search_dirs."""
        candidates: list[Path] = []
        # work_dir (nom exact et variantes usuelles)
        candidates.extend((work_dir / f"{video_id}.{suf}") for suf in ("srt", "vtt"))
        candidates.extend((work_dir / f"{video_id}.en.{suf}") for suf in ("srt", "vtt"))
        # répertoires custom
        extra_dirs: List[Path] = [Path("./custom")]
        try:
            cfg_dirs = list(getattr(self.settings, 'search_dirs', []) or [])
            if cfg_dirs:
                extra_dirs = cfg_dirs
        except Exception:
            pass
        for d in extra_dirs:
            d = Path(d)
            candidates.extend((d / f"{video_id}.{suf}") for suf in ("srt", "vtt"))
            candidates.extend((d / f"{video_id}.en.{suf}") for suf in ("srt", "vtt"))
            if d.exists():
                # nouveau pattern: <title>-<video_id>.<lang>.<ext> ou <title>-<video_id>.<ext>
                for p in d.glob(f"*-{video_id}.*"):
                    if p.suffix.lower() in (".srt", ".vtt"):
                        candidates.append(p)
                for p in d.glob(f"{video_id}.*"):
                    if p.suffix.lower() in (".srt", ".vtt"):
                        candidates.append(p)
        # glob élargi dans work_dir
        for p in work_dir.glob(f"*-{video_id}.*"):
            if p.suffix.lower() in (".srt", ".vtt"):
                candidates.append(p)
        for p in work_dir.glob(f"{video_id}.*"):
            if p.suffix.lower() in (".srt", ".vtt"):
                candidates.append(p)

        seen = set()
        for c in candidates:
            if c in seen:
                continue
            seen.add(c)
            if c.exists() and c.stat().st_size > 0:
                try:
                    return self.parser.parse_file(c)
                except Exception:
                    continue
        return None

    def validate_subtitle_sync(self, subtitle_file: SubtitleFile, video_duration_s: float) -> bool:
        """Valide que les sous-titres sont plausiblement synchronisés avec la vidéo.

        - Accepte les fichiers vides
        - Refuse si un sous-titre dépasse largement la durée vidéo (tolérance 30s)
        - Refuse si l'ordre chronologique est inversé
        """
        if not subtitle_file.entries:
            return True

        max_subtitle_time = max(entry.end_s for entry in subtitle_file.entries)
        tolerance_s = 30.0
        if max_subtitle_time > video_duration_s + tolerance_s:
            return False

        for i in range(1, len(subtitle_file.entries)):
            if subtitle_file.entries[i].start_s < subtitle_file.entries[i - 1].start_s:
                return False

        return True


def create_subtitle_downloader(
    settings: SubtitleSettings,
    youtube_provider: Optional[YouTubeProvider] = None
) -> SubtitleDownloader:
    """Factory function pour créer un SubtitleDownloader."""
    return SubtitleDownloader(settings, youtube_provider)
