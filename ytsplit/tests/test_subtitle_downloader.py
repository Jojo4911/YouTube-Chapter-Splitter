"""Tests pour le downloader de sous-titres."""

import pytest
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch, MagicMock

from ..config import SubtitleSettings
from ..providers.youtube import YouTubeProvider, YouTubeError
from ..subtitles.models import SubtitleFile, SubtitleEntry
from ..subtitles.downloader import SubtitleDownloader, SubtitleDownloadError, create_subtitle_downloader
from ..subtitles.parser import SubtitleParser


class TestSubtitleDownloader:
    """Tests pour SubtitleDownloader."""
    
    @pytest.fixture
    def subtitle_settings(self):
        """Configuration par défaut."""
        return SubtitleSettings(
            enabled=True,
            auto_download=True,
            languages=["fr", "en"],
            format_priority=["srt", "vtt"],
            encoding="utf-8"
        )
    
    @pytest.fixture
    def mock_youtube_provider(self):
        """Provider YouTube mocké."""
        return Mock(spec=YouTubeProvider)
    
    @pytest.fixture
    def mock_parser(self):
        """Parser mocké."""
        return Mock(spec=SubtitleParser)
    
    @pytest.fixture
    def downloader(self, subtitle_settings, mock_youtube_provider):
        """Downloader avec provider mocké."""
        return SubtitleDownloader(subtitle_settings, mock_youtube_provider)
    
    @pytest.fixture
    def sample_subtitle_file(self):
        """Fichier de sous-titres de test."""
        entries = [
            SubtitleEntry(index=1, start_s=0.0, end_s=2.0, content="Premier"),
            SubtitleEntry(index=2, start_s=3.0, end_s=5.0, content="Deuxième"),
        ]
        return SubtitleFile(
            file_path=Path("test.srt"),
            language="fr",
            format="srt",
            entries=entries,
            encoding="utf-8"
        )
    
    def test_get_subtitle_file_external_srt(self, mock_youtube_provider, sample_subtitle_file):
        """Test récupération fichier SRT externe."""
        with tempfile.NamedTemporaryFile(mode='w', suffix=".srt", delete=False) as f:
            f.write("1\n00:00:01,000 --> 00:00:03,000\nTest\n")
            external_path = Path(f.name)
        
        try:
            settings = SubtitleSettings(
                enabled=True,
                external_srt_path=external_path
            )
            
            downloader = SubtitleDownloader(settings, mock_youtube_provider)
            
            with patch.object(downloader.parser, 'parse_file', return_value=sample_subtitle_file):
                result = downloader.get_subtitle_file("https://youtube.com/watch?v=test", "test_id", Path("."))
                
                assert result == sample_subtitle_file
                downloader.parser.parse_file.assert_called_once_with(external_path)
        
        finally:
            external_path.unlink()
    
    def test_get_subtitle_file_external_srt_error(self, mock_youtube_provider):
        """Test erreur fichier SRT externe."""
        settings = SubtitleSettings(
            enabled=True,
            external_srt_path=Path("nonexistent.srt")
        )
        
        downloader = SubtitleDownloader(settings, mock_youtube_provider)
        
        with patch.object(downloader.parser, 'parse_file', side_effect=Exception("Parse error")):
            with pytest.raises(SubtitleDownloadError, match="Erreur lors du parsing du fichier externe"):
                downloader.get_subtitle_file("https://youtube.com/watch?v=test", "test_id", Path("."))
    
    def test_get_subtitle_file_auto_download_success(self, downloader, sample_subtitle_file, mock_youtube_provider):
        """Test téléchargement automatique réussi."""
        mock_youtube_provider.get_subtitles_file_path.return_value = None  # Pas de fichier existant
        mock_youtube_provider.download_subtitles.return_value = Path("downloaded.srt")
        
        with patch.object(downloader.parser, 'parse_file', return_value=sample_subtitle_file):
            result = downloader.get_subtitle_file("https://youtube.com/watch?v=test", "test_id", Path("."))
            
            assert result == sample_subtitle_file
            mock_youtube_provider.download_subtitles.assert_called_once()
    
    def test_get_subtitle_file_auto_download_no_subtitles(self, downloader, mock_youtube_provider):
        """Test téléchargement automatique sans sous-titres."""
        mock_youtube_provider.get_subtitles_file_path.return_value = None
        mock_youtube_provider.download_subtitles.return_value = None  # Pas de sous-titres disponibles
        
        result = downloader.get_subtitle_file("https://youtube.com/watch?v=test", "test_id", Path("."))
        
        assert result is None
    
    def test_get_subtitle_file_auto_download_error(self, downloader, mock_youtube_provider):
        """Test erreur lors du téléchargement automatique."""
        mock_youtube_provider.get_subtitles_file_path.return_value = None
        mock_youtube_provider.download_subtitles.side_effect = YouTubeError("Download failed")
        
        # Les erreurs de téléchargement ne doivent pas être critiques
        result = downloader.get_subtitle_file("https://youtube.com/watch?v=test", "test_id", Path("."))
        
        assert result is None
    
    def test_get_subtitle_file_existing_file(self, downloader, sample_subtitle_file, mock_youtube_provider):
        """Test fichier existant trouvé."""
        existing_path = Path("existing.srt")
        mock_youtube_provider.get_subtitles_file_path.return_value = existing_path
        
        with patch.object(downloader.parser, 'parse_file', return_value=sample_subtitle_file):
            result = downloader.get_subtitle_file("https://youtube.com/watch?v=test", "test_id", Path("."))
            
            assert result == sample_subtitle_file
            downloader.parser.parse_file.assert_called_once_with(existing_path)
    
    def test_get_subtitle_file_force_redownload(self, mock_youtube_provider, sample_subtitle_file):
        """Test force redownload."""
        settings = SubtitleSettings(
            enabled=True,
            auto_download=True,
            force_redownload=True
        )
        
        downloader = SubtitleDownloader(settings, mock_youtube_provider)
        
        # Même si un fichier existant est présent
        mock_youtube_provider.get_subtitles_file_path.return_value = Path("existing.srt")
        mock_youtube_provider.download_subtitles.return_value = Path("new.srt")
        
        with patch.object(downloader.parser, 'parse_file', return_value=sample_subtitle_file):
            result = downloader.get_subtitle_file("https://youtube.com/watch?v=test", "test_id", Path("."))
            
            # Le téléchargement doit être forcé
            mock_youtube_provider.download_subtitles.assert_called_once()
            assert result == sample_subtitle_file
    
    def test_get_subtitle_file_no_provider(self):
        """Test sans provider YouTube."""
        settings = SubtitleSettings(
            enabled=True,
            auto_download=True
        )
        
        downloader = SubtitleDownloader(settings, None)  # Pas de provider
        
        result = downloader.get_subtitle_file("https://youtube.com/watch?v=test", "test_id", Path("."))
        
        assert result is None
    
    def test_download_from_youtube_success(self, downloader, sample_subtitle_file, mock_youtube_provider):
        """Test téléchargement depuis YouTube réussi."""
        mock_youtube_provider.get_subtitles_file_path.return_value = None  # Pas de fichier existant
        mock_youtube_provider.download_subtitles.return_value = Path("downloaded.srt")
        
        with patch.object(downloader.parser, 'parse_file', return_value=sample_subtitle_file):
            result = downloader._download_from_youtube("https://youtube.com/watch?v=test", "test_id", Path("."))
            
            assert result == sample_subtitle_file
            mock_youtube_provider.download_subtitles.assert_called_once_with(
                url="https://youtube.com/watch?v=test",
                languages=["fr", "en"],
                format_priority=["srt", "vtt"],
                output_dir=Path(".")
            )
    
    def test_download_from_youtube_existing_file(self, downloader, sample_subtitle_file, mock_youtube_provider):
        """Test utilisation fichier existant."""
        existing_path = Path("existing.srt")
        mock_youtube_provider.get_subtitles_file_path.return_value = existing_path
        
        with patch.object(downloader.parser, 'parse_file', return_value=sample_subtitle_file):
            result = downloader._download_from_youtube("https://youtube.com/watch?v=test", "test_id", Path("."))
            
            assert result == sample_subtitle_file
            # Pas d'appel au téléchargement car fichier existant trouvé
            mock_youtube_provider.download_subtitles.assert_not_called()
    
    def test_download_from_youtube_no_provider(self, subtitle_settings):
        """Test sans provider YouTube."""
        downloader = SubtitleDownloader(subtitle_settings, None)
        
        with pytest.raises(SubtitleDownloadError, match="Provider YouTube non configuré"):
            downloader._download_from_youtube("https://youtube.com/watch?v=test", "test_id", Path("."))
    
    def test_find_existing_subtitle_file_found(self, downloader, sample_subtitle_file, mock_youtube_provider):
        """Test recherche fichier existant trouvé."""
        existing_path = Path("found.srt")
        mock_youtube_provider.get_subtitles_file_path.return_value = existing_path
        
        with patch.object(downloader.parser, 'parse_file', return_value=sample_subtitle_file):
            result = downloader._find_existing_subtitle_file("test_id", Path("."))
            
            assert result == sample_subtitle_file
    
    def test_find_existing_subtitle_file_not_found(self, downloader, mock_youtube_provider):
        """Test recherche fichier existant non trouvé."""
        mock_youtube_provider.get_subtitles_file_path.return_value = None
        
        result = downloader._find_existing_subtitle_file("test_id", Path("."))
        
        assert result is None
    
    def test_find_existing_subtitle_file_parse_error(self, downloader, mock_youtube_provider):
        """Test erreur parsing fichier existant."""
        existing_path = Path("corrupted.srt")
        mock_youtube_provider.get_subtitles_file_path.return_value = existing_path
        
        with patch.object(downloader.parser, 'parse_file', side_effect=Exception("Corrupted file")):
            result = downloader._find_existing_subtitle_file("test_id", Path("."))
            
            assert result is None  # Erreur ignorée
    
    def test_list_available_subtitles_success(self, downloader, mock_youtube_provider):
        """Test liste sous-titres disponibles."""
        available_subs = {"fr": ["srt", "vtt"], "en": ["srt"]}
        mock_youtube_provider.get_available_subtitles.return_value = available_subs
        
        result = downloader.list_available_subtitles("https://youtube.com/watch?v=test")
        
        assert result == available_subs
    
    def test_list_available_subtitles_error(self, downloader, mock_youtube_provider):
        """Test erreur lors de la liste des sous-titres."""
        mock_youtube_provider.get_available_subtitles.side_effect = YouTubeError("API Error")
        
        result = downloader.list_available_subtitles("https://youtube.com/watch?v=test")
        
        assert result is None
    
    def test_list_available_subtitles_no_provider(self, subtitle_settings):
        """Test liste sans provider."""
        downloader = SubtitleDownloader(subtitle_settings, None)
        
        result = downloader.list_available_subtitles("https://youtube.com/watch?v=test")
        
        assert result is None
    
    def test_validate_subtitle_sync_valid(self, downloader, sample_subtitle_file):
        """Test validation synchronisation valide."""
        video_duration = 10.0  # 10 secondes
        
        # Dernier sous-titre se termine à 5s, bien avant la fin vidéo
        result = downloader.validate_subtitle_sync(sample_subtitle_file, video_duration)
        
        assert result is True
    
    def test_validate_subtitle_sync_too_long(self, downloader):
        """Test sous-titres trop longs par rapport à la vidéo."""
        entries = [
            SubtitleEntry(index=1, start_s=0.0, end_s=50.0, content="Trop long"),
        ]
        subtitle_file = SubtitleFile(
            file_path=Path("test.srt"),
            format="srt",
            entries=entries
        )
        
        video_duration = 10.0  # Vidéo de 10s, sous-titre jusqu'à 50s
        
        result = downloader.validate_subtitle_sync(subtitle_file, video_duration)
        
        assert result is False
    
    def test_validate_subtitle_sync_empty_file(self, downloader):
        """Test validation fichier vide."""
        empty_subtitle_file = SubtitleFile(
            file_path=Path("empty.srt"),
            format="srt",
            entries=[]
        )
        
        result = downloader.validate_subtitle_sync(empty_subtitle_file, 100.0)
        
        assert result is True  # Fichier vide considéré comme valide
    
    def test_validate_subtitle_sync_chronological_order(self, downloader):
        """Test validation ordre chronologique."""
        # Sous-titres non ordonnés
        entries = [
            SubtitleEntry(index=1, start_s=5.0, end_s=7.0, content="Deuxième"),
            SubtitleEntry(index=2, start_s=0.0, end_s=2.0, content="Premier"),
        ]
        subtitle_file = SubtitleFile(
            file_path=Path("test.srt"),
            format="srt",
            entries=entries
        )
        
        result = downloader.validate_subtitle_sync(subtitle_file, 10.0)
        
        assert result is False  # Ordre incorrect
    
    def test_validate_subtitle_sync_with_tolerance(self, downloader):
        """Test validation avec tolérance."""
        entries = [
            SubtitleEntry(index=1, start_s=0.0, end_s=15.0, content="Dans tolérance"),
        ]
        subtitle_file = SubtitleFile(
            file_path=Path("test.srt"),
            format="srt",
            entries=entries
        )
        
        video_duration = 10.0  # 10s vidéo, 15s sous-titre, mais dans la tolérance de 30s
        
        result = downloader.validate_subtitle_sync(subtitle_file, video_duration)
        
        assert result is True  # Dans la tolérance
    
    def test_factory_function(self, subtitle_settings, mock_youtube_provider):
        """Test fonction factory."""
        downloader = create_subtitle_downloader(subtitle_settings, mock_youtube_provider)
        
        assert isinstance(downloader, SubtitleDownloader)
        assert downloader.settings == subtitle_settings
        assert downloader.youtube_provider == mock_youtube_provider


class TestSubtitleDownloaderIntegration:
    """Tests d'intégration pour SubtitleDownloader."""
    
    def test_complete_workflow_with_external_file(self):
        """Test workflow complet avec fichier externe."""
        with tempfile.NamedTemporaryFile(mode='w', suffix=".srt", encoding='utf-8', delete=False) as f:
            f.write("""1
00:00:01,000 --> 00:00:03,000
Premier sous-titre

2
00:00:05,000 --> 00:00:07,000
Deuxième sous-titre
""")
            external_path = Path(f.name)
        
        try:
            settings = SubtitleSettings(
                enabled=True,
                external_srt_path=external_path,
                encoding="utf-8"
            )
            
            # Pas de provider nécessaire pour fichier externe
            downloader = SubtitleDownloader(settings, None)
            
            result = downloader.get_subtitle_file("", "", Path("."))
            
            assert result is not None
            assert result.format == "srt"
            assert len(result.entries) == 2
            assert result.entries[0].content == "Premier sous-titre"
            assert result.entries[1].content == "Deuxième sous-titre"
            
        finally:
            external_path.unlink()