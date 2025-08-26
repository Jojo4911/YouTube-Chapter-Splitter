"""Tests pour le module YouTube provider."""

import pytest
import json
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path
import subprocess

from ytsplit.providers.youtube import YouTubeProvider, YouTubeError, create_youtube_provider
from ytsplit.config import Settings
from ytsplit.models import VideoMeta, Chapter


class TestYouTubeProvider:
    """Tests pour la classe YouTubeProvider."""
    
    @pytest.fixture
    def settings(self):
        """Settings de test."""
        return Settings(
            work_dir=Path("./test_cache"),
            yt_dlp_format="best[height<=720]",
            video_format="mp4"
        )
    
    @pytest.fixture
    def provider(self, settings):
        """Provider YouTube mocké."""
        with patch.object(YouTubeProvider, '_validate_ytdlp'):
            return YouTubeProvider(settings)
    
    def test_validate_youtube_url_valid_urls(self, provider):
        """Test de validation d'URLs YouTube valides."""
        valid_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=123s",
            "https://m.youtube.com/watch?v=dQw4w9WgXcQ"
        ]
        
        for url in valid_urls:
            assert provider.validate_youtube_url(url) == True
    
    def test_validate_youtube_url_invalid_urls(self, provider):
        """Test de validation d'URLs invalides."""
        invalid_urls = [
            "https://example.com/video",
            "https://vimeo.com/123456789",
            "https://www.youtube.com/",
            "https://www.youtube.com/watch",
            "https://www.youtube.com/watch?v=invalid",
            "not_a_url",
            "",
            "https://youtu.be/",
            "https://youtu.be/invalid_id"
        ]
        
        for url in invalid_urls:
            assert provider.validate_youtube_url(url) == False
    
    def test_extract_video_id(self, provider):
        """Test d'extraction d'ID vidéo."""
        test_cases = [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtube.com/watch?v=abc123XYZ-_&t=123", "abc123XYZ-_")
        ]
        
        for url, expected_id in test_cases:
            assert provider.extract_video_id(url) == expected_id
    
    def test_extract_video_id_invalid_url(self, provider):
        """Test d'extraction d'ID avec URL invalide."""
        with pytest.raises(YouTubeError, match="URL YouTube invalide"):
            provider.extract_video_id("https://example.com/video")
    
    @patch('subprocess.run')
    def test_validate_ytdlp_success(self, mock_run):
        """Test de validation yt-dlp réussie."""
        mock_run.return_value = Mock(returncode=0, stdout="2023.07.06")
        
        # Ne doit pas lever d'exception
        provider = YouTubeProvider(Settings())
        assert isinstance(provider, YouTubeProvider)
    
    @patch('subprocess.run')
    def test_validate_ytdlp_not_found(self, mock_run):
        """Test de validation yt-dlp non trouvé."""
        mock_run.side_effect = FileNotFoundError("yt-dlp not found")
        
        with pytest.raises(YouTubeError, match="yt-dlp n'est pas disponible"):
            YouTubeProvider(Settings())
    
    @patch('subprocess.run')
    def test_validate_ytdlp_fails(self, mock_run):
        """Test de validation yt-dlp échec."""
        mock_run.return_value = Mock(returncode=1, stderr="Error")
        
        with pytest.raises(YouTubeError, match="yt-dlp n'est pas correctement installé"):
            YouTubeProvider(Settings())
    
    def test_extract_chapters_from_info_with_chapters(self, provider):
        """Test d'extraction de chapitres depuis info yt-dlp."""
        info = {
            "chapters": [
                {"start_time": 0, "end_time": 120, "title": "Introduction"},
                {"start_time": 120, "end_time": 300, "title": "Partie 1"},
                {"start_time": 300, "end_time": 450, "title": "Conclusion"}
            ]
        }
        
        chapters = provider._extract_chapters_from_info(info)
        
        assert len(chapters) == 3
        assert chapters[0].title == "Introduction"
        assert chapters[0].start_s == 0.0
        assert chapters[0].end_s == 120.0
        assert chapters[1].title == "Partie 1"
        assert chapters[2].title == "Conclusion"
    
    def test_extract_chapters_from_info_no_chapters(self, provider):
        """Test d'extraction sans chapitres."""
        info = {}
        chapters = provider._extract_chapters_from_info(info)
        assert len(chapters) == 0
    
    def test_extract_chapters_from_info_invalid_chapters(self, provider):
        """Test d'extraction avec chapitres invalides."""
        info = {
            "chapters": [
                {"start_time": 100, "end_time": 50, "title": "Invalid"},  # end < start
                {"start_time": 120, "end_time": 300, "title": "Valid"}
            ]
        }
        
        chapters = provider._extract_chapters_from_info(info)
        assert len(chapters) == 1
        assert chapters[0].title == "Valid"
    
    @patch('subprocess.run')
    def test_get_video_info_success(self, mock_run, provider):
        """Test de récupération d'infos vidéo réussie."""
        mock_info = {
            "id": "dQw4w9WgXcQ",
            "title": "Test Video",
            "duration": 180,
            "chapters": [
                {"start_time": 0, "end_time": 90, "title": "Part 1"},
                {"start_time": 90, "end_time": 180, "title": "Part 2"}
            ]
        }
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(mock_info),
            stderr=""
        )
        
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        meta = provider.get_video_info(url)
        
        assert isinstance(meta, VideoMeta)
        assert meta.video_id == "dQw4w9WgXcQ"
        assert meta.title == "Test Video"
        assert meta.duration_s == 180.0
        assert len(meta.chapters) == 2
        assert meta.url == url
    
    @patch('subprocess.run')
    def test_get_video_info_no_chapters(self, mock_run, provider):
        """Test de récupération d'infos sans chapitres."""
        mock_info = {
            "id": "abcdefghijk",
            "title": "Video sans chapitres",
            "duration": 120
        }
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(mock_info),
            stderr=""
        )
        
        meta = provider.get_video_info("https://www.youtube.com/watch?v=abcdefghijk")
        
        # Doit créer un chapitre unique
        assert len(meta.chapters) == 1
        assert meta.chapters[0].title == "Video sans chapitres"
        assert meta.chapters[0].start_s == 0.0
        assert meta.chapters[0].end_s == 120.0
    
    @patch('subprocess.run')
    def test_get_video_info_ytdlp_error(self, mock_run, provider):
        """Test d'erreur yt-dlp lors de l'extraction."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="ERROR: Video unavailable"
        )
        
        with pytest.raises(YouTubeError, match="Échec de l'extraction des métadonnées"):
            provider.get_video_info("https://www.youtube.com/watch?v=invalidvid1")
    
    @patch('subprocess.run')
    def test_get_video_info_invalid_json(self, mock_run, provider):
        """Test de réponse JSON invalide."""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="invalid json",
            stderr=""
        )
        
        with pytest.raises(YouTubeError, match="Réponse JSON invalide"):
            provider.get_video_info("https://www.youtube.com/watch?v=invalidjson")
    
    @patch('subprocess.run')
    def test_get_video_info_missing_data(self, mock_run, provider):
        """Test avec données manquantes."""
        mock_info = {"title": "Test"}  # Pas d'ID ni de durée
        
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(mock_info),
            stderr=""
        )
        
        with pytest.raises(YouTubeError, match="ID vidéo manquant"):
            provider.get_video_info("https://www.youtube.com/watch?v=missingdata")
    
    def test_get_video_file_path_exists(self, provider, tmp_path):
        """Test de recherche de fichier existant."""
        # Créer un fichier temporaire
        video_file = tmp_path / "test123.mp4"
        video_file.write_text("fake video content")
        
        result = provider.get_video_file_path("test123", tmp_path)
        assert result == video_file
    
    def test_get_video_file_path_not_exists(self, provider, tmp_path):
        """Test de recherche de fichier inexistant."""
        result = provider.get_video_file_path("nonexistent", tmp_path)
        assert result is None
    
    def test_get_video_file_path_empty_file(self, provider, tmp_path):
        """Test avec fichier vide (ignoré)."""
        # Créer un fichier vide
        video_file = tmp_path / "test123.mp4"
        video_file.touch()
        
        result = provider.get_video_file_path("test123", tmp_path)
        assert result is None
    
    @patch('subprocess.run')
    def test_download_video_success(self, mock_run, provider, tmp_path):
        """Test de téléchargement réussi."""
        # Créer le fichier de sortie simulé
        expected_file = tmp_path / "dQw4w9WgXcQ.mp4"
        expected_file.write_text("fake video content")
        
        mock_run.return_value = Mock(returncode=0, stderr="")
        
        with patch.object(provider.settings, 'work_dir', tmp_path):
            result = provider.download_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            
            assert result == expected_file
            assert result.exists()
    
    @patch('subprocess.run')
    def test_download_video_ytdlp_error(self, mock_run, provider):
        """Test d'erreur lors du téléchargement."""
        mock_run.return_value = Mock(
            returncode=1,
            stderr="ERROR: Video unavailable"
        )
        
        with pytest.raises(YouTubeError, match="Échec du téléchargement"):
            provider.download_video("https://www.youtube.com/watch?v=invalidvid2")


class TestCreateYouTubeProvider:
    """Tests pour la factory function."""
    
    @patch.object(YouTubeProvider, '_validate_ytdlp')
    def test_create_provider_with_settings(self, mock_validate):
        """Test de création avec settings personnalisés."""
        settings = Settings(work_dir=Path("custom"))
        provider = create_youtube_provider(settings)
        
        assert isinstance(provider, YouTubeProvider)
        assert provider.settings.work_dir == Path("custom")
    
    @patch.object(YouTubeProvider, '_validate_ytdlp')
    def test_create_provider_default_settings(self, mock_validate):
        """Test de création avec settings par défaut."""
        provider = create_youtube_provider()
        
        assert isinstance(provider, YouTubeProvider)
        assert provider.settings.work_dir == Path("./cache")