"""Tests pour le module FFmpeg."""

import pytest
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path
import subprocess

from ytsplit.cutting.ffmpeg import FFmpegCutter, FFmpegError, create_ffmpeg_cutter
from ytsplit.config import Settings
from ytsplit.models import SplitPlanItem, SplitResult


class TestFFmpegCutter:
    """Tests pour la classe FFmpegCutter."""
    
    @pytest.fixture
    def settings(self):
        """Settings de test."""
        return Settings(
            work_dir=Path("./test_work"),
            out_dir=Path("./test_output"),
            x264={'crf': 20, 'preset': 'veryfast'},
            audio={'codec': 'aac', 'bitrate': '128k'},
            video_format='mp4',
            validation={'tolerance_seconds': 0.2, 'max_retries': 1}
        )
    
    @pytest.fixture
    def cutter(self, settings):
        """FFmpegCutter mocké."""
        with patch.object(FFmpegCutter, '_validate_ffmpeg'):
            return FFmpegCutter(settings)
    
    @pytest.fixture
    def plan_item(self, tmp_path):
        """Item de plan de test."""
        return SplitPlanItem(
            video_id="test123",
            chapter_index=1,
            chapter_title="Test Chapter",
            start_s=10.0,
            end_s=70.0,
            expected_duration_s=60.0,
            output_path=tmp_path / "01 - Test Chapter.mp4"
        )
    
    @patch('subprocess.run')
    def test_validate_ffmpeg_success(self, mock_run):
        """Test de validation FFmpeg réussie."""
        mock_run.return_value = Mock(returncode=0)
        
        # Ne doit pas lever d'exception
        cutter = FFmpegCutter(Settings())
        assert isinstance(cutter, FFmpegCutter)
    
    @patch('subprocess.run')
    def test_validate_ffmpeg_not_found(self, mock_run):
        """Test FFmpeg non trouvé."""
        mock_run.side_effect = FileNotFoundError("ffmpeg not found")
        
        with pytest.raises(FFmpegError, match="FFmpeg n'est pas disponible"):
            FFmpegCutter(Settings())
    
    @patch('subprocess.run')
    def test_validate_ffmpeg_fails(self, mock_run):
        """Test FFmpeg échoue."""
        mock_run.return_value = Mock(returncode=1)
        
        with pytest.raises(FFmpegError, match="FFmpeg n'est pas correctement installé"):
            FFmpegCutter(Settings())
    
    def test_build_ffmpeg_command(self, cutter, plan_item):
        """Test de construction de commande FFmpeg."""
        source_path = Path("source.mp4")
        
        cmd = cutter._build_ffmpeg_command(source_path, plan_item)
        
        # Vérifications de base
        assert cmd[0] == "ffmpeg"
        assert "-i" in cmd
        assert str(source_path) in cmd
        assert "-ss" in cmd
        assert "-to" in cmd
        # Les timestamps sont dans la commande mais pas forcément exactement sous cette forme
        assert any("00:00:10" in str(arg) for arg in cmd)  # start_s formaté
        assert any("00:01:10" in str(arg) for arg in cmd)  # end_s formaté
        assert "-c:v" in cmd
        assert "libx264" in cmd
        assert str(plan_item.output_path) in cmd
    
    @patch('ytsplit.utils.ffprobe.get_video_duration')
    @patch('subprocess.run')
    def test_cut_precise_success(self, mock_run, mock_duration, cutter, plan_item, tmp_path):
        """Test de découpage réussi."""
        # Setup
        source_path = tmp_path / "source.mp4"
        source_path.write_text("fake video")
        
        mock_run.return_value = Mock(returncode=0, stderr="")
        mock_duration.return_value = 59.9  # Durée dans la tolérance de 0.2s
        
        # Créer le fichier de sortie simulé
        plan_item.output_path.parent.mkdir(parents=True, exist_ok=True)
        plan_item.output_path.write_text("fake output")
        
        # Exécution
        result = cutter.cut_precise(source_path, plan_item)
        
        # Vérifications
        assert isinstance(result, SplitResult)
        assert result.status == "OK"
        assert result.obtained_duration_s == 59.9
        assert result.processing_time_s >= 0
    
    @patch('subprocess.run')
    def test_cut_precise_ffmpeg_error(self, mock_run, cutter, plan_item, tmp_path):
        """Test d'erreur FFmpeg."""
        # Setup
        source_path = tmp_path / "source.mp4"
        source_path.write_text("fake video")
        
        mock_run.return_value = Mock(returncode=1, stderr="FFmpeg error")
        
        # Exécution
        result = cutter.cut_precise(source_path, plan_item)
        
        # Vérifications
        assert result.status == "ERR"
        assert "FFmpeg a échoué" in result.message
        assert result.obtained_duration_s is None
    
    def test_cut_precise_source_not_found(self, cutter, plan_item):
        """Test avec fichier source manquant."""
        source_path = Path("nonexistent.mp4")
        
        result = cutter.cut_precise(source_path, plan_item)
        
        assert result.status == "ERR"
        assert "Fichier source introuvable" in result.message
    
    @patch('ytsplit.utils.ffprobe.get_video_duration')
    @patch('subprocess.run')
    def test_cut_precise_duration_tolerance(self, mock_run, mock_duration, cutter, plan_item, tmp_path):
        """Test de tolérance de durée."""
        # Setup
        source_path = tmp_path / "source.mp4"
        source_path.write_text("fake video")
        
        mock_run.return_value = Mock(returncode=0, stderr="")
        mock_duration.return_value = 58.0  # 2 secondes d'écart avec 60s attendu
        
        plan_item.output_path.parent.mkdir(parents=True, exist_ok=True)
        plan_item.output_path.write_text("fake output")
        
        # Exécution
        result = cutter.cut_precise(source_path, plan_item)
        
        # Vérifications (écart de 2s > tolérance de 0.2s)
        assert result.status == "ERR"
        assert result.obtained_duration_s == 58.0
        assert "Erreur de durée" in result.message
    
    @patch('subprocess.run')
    def test_cut_precise_timeout(self, mock_run, cutter, plan_item, tmp_path):
        """Test de timeout FFmpeg."""
        # Setup
        source_path = tmp_path / "source.mp4"
        source_path.write_text("fake video")
        
        mock_run.side_effect = subprocess.TimeoutExpired("ffmpeg", 300)
        
        # Exécution
        result = cutter.cut_precise(source_path, plan_item)
        
        # Vérifications
        assert result.status == "ERR"
        assert "Timeout FFmpeg" in result.message
    
    @patch('ytsplit.utils.ffprobe.get_video_duration')
    @patch('subprocess.run')
    def test_retry_with_slower_preset(self, mock_run, mock_duration, cutter, plan_item, tmp_path):
        """Test de retry avec preset plus lent."""
        # Setup
        source_path = tmp_path / "source.mp4"
        source_path.write_text("fake video")
        
        # Premier appel échoue, deuxième réussit
        mock_run.side_effect = [
            Mock(returncode=1, stderr="First error"),  # Premier échec
            Mock(returncode=0, stderr="")  # Retry réussi
        ]
        mock_duration.return_value = 60.0
        
        plan_item.output_path.parent.mkdir(parents=True, exist_ok=True)
        plan_item.output_path.write_text("fake output")
        
        # Exécution
        result = cutter.cut_precise(source_path, plan_item)
        
        # Vérifications
        assert result.status == "OK"
        assert "retry" in result.message.lower()
    
    @patch('ytsplit.utils.ffprobe.get_video_duration')
    def test_is_output_valid(self, mock_duration, cutter, plan_item, tmp_path):
        """Test de validation de fichier de sortie."""
        # Fichier inexistant
        assert cutter._is_output_valid(plan_item) == False
        
        # Fichier vide
        plan_item.output_path.parent.mkdir(parents=True, exist_ok=True)
        plan_item.output_path.touch()
        assert cutter._is_output_valid(plan_item) == False
        
        # Fichier valide
        plan_item.output_path.write_text("fake content")
        mock_duration.return_value = 60.1  # Dans la tolérance
        assert cutter._is_output_valid(plan_item) == True
        
        # Fichier avec durée incorrecte
        mock_duration.return_value = 50.0  # Hors tolérance
        assert cutter._is_output_valid(plan_item) == False


class TestCreateFFmpegCutter:
    """Tests pour la factory function."""
    
    @patch.object(FFmpegCutter, '_validate_ffmpeg')
    def test_create_cutter_with_settings(self, mock_validate):
        """Test de création avec settings personnalisés."""
        settings = Settings(x264={'crf': 25, 'preset': 'fast'})
        cutter = create_ffmpeg_cutter(settings)
        
        assert isinstance(cutter, FFmpegCutter)
        assert cutter.settings.x264.crf == 25
    
    @patch.object(FFmpegCutter, '_validate_ffmpeg')
    def test_create_cutter_default_settings(self, mock_validate):
        """Test de création avec settings par défaut."""
        cutter = create_ffmpeg_cutter()
        
        assert isinstance(cutter, FFmpegCutter)
        assert cutter.settings.x264.crf == 18  # Valeur par défaut