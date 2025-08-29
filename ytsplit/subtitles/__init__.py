"""Module de gestion des sous-titres pour YouTube Chapter Splitter."""

from .models import SubtitleEntry, SubtitleFile, SubtitleSliceResult
from .parser import SubtitleParser, SubtitleParseError, create_subtitle_parser
from .slicer import SubtitleSlicer
from .downloader import SubtitleDownloader

def create_subtitle_slicer(settings=None):
    """Créer un slicer de sous-titres avec les paramètres par défaut."""
    if settings is None:
        from ..config import SubtitleSettings
        settings = SubtitleSettings()
    return SubtitleSlicer(settings)

__all__ = [
    "SubtitleEntry",
    "SubtitleFile", 
    "SubtitleSliceResult",
    "SubtitleParser",
    "SubtitleParseError",
    "SubtitleSlicer",
    "SubtitleDownloader",
    "create_subtitle_parser",
    "create_subtitle_slicer",
]