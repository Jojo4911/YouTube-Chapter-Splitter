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


class TestFFmpegCrop:
    """Tests pour les fonctionnalités de crop."""
    
    @pytest.fixture
    def settings_with_crop(self):
        """Settings avec crop activé."""
        return Settings(
            crop={'enabled': True, 'bottom': 40, 'top': 0, 'left': 0, 'right': 0}
        )
    
    @pytest.fixture
    def cutter_with_crop(self, settings_with_crop):
        """Cutter avec crop activé."""
        with patch.object(FFmpegCutter, '_validate_ffmpeg'):
            return FFmpegCutter(settings_with_crop)
    
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
    
    @patch('ytsplit.utils.ffprobe.get_video_resolution')
    def test_build_crop_filter_bottom_only(self, mock_resolution, cutter_with_crop, tmp_path):
        """Test de construction filtre crop pour bottom seulement."""
        mock_resolution.return_value = (1920, 1080)  # Full HD
        
        source_path = tmp_path / "source.mp4"
        source_path.write_text("fake video")
        
        crop_filter = cutter_with_crop._build_crop_filter(source_path)
        
        # Vérifications
        assert crop_filter == "crop=1920:1040:0:0"  # 1080-40=1040 hauteur
        mock_resolution.assert_called_once_with(source_path)
    
    @patch('ytsplit.utils.ffprobe.get_video_resolution')
    def test_build_crop_filter_all_sides(self, mock_resolution, tmp_path):
        """Test de crop sur tous les côtés."""
        # Settings avec crop sur tous les côtés
        settings = Settings(
            crop={'enabled': True, 'top': 20, 'bottom': 40, 'left': 10, 'right': 30}
        )
        with patch.object(FFmpegCutter, '_validate_ffmpeg'):
            cutter = FFmpegCutter(settings)
        
        mock_resolution.return_value = (1920, 1080)
        source_path = tmp_path / "source.mp4"
        source_path.write_text("fake video")
        
        crop_filter = cutter._build_crop_filter(source_path)
        
        # Calculs attendus:
        # width: 1920 - 10 - 30 = 1880
        # height: 1080 - 20 - 40 = 1020
        # x (left offset): 10
        # y (top offset): 20
        assert crop_filter == "crop=1880:1020:10:20"
    
    @patch('ytsplit.utils.ffprobe.get_video_resolution')
    def test_build_crop_filter_no_crop_needed(self, mock_resolution, tmp_path):
        """Test quand aucun crop n'est nécessaire (tous à 0)."""
        settings = Settings(
            crop={'enabled': True, 'top': 0, 'bottom': 0, 'left': 0, 'right': 0}
        )
        with patch.object(FFmpegCutter, '_validate_ffmpeg'):
            cutter = FFmpegCutter(settings)
        
        mock_resolution.return_value = (1920, 1080)
        source_path = tmp_path / "source.mp4"
        source_path.write_text("fake video")
        
        crop_filter = cutter._build_crop_filter(source_path)
        
        assert crop_filter is None  # Pas de crop nécessaire
    
    @patch('ytsplit.utils.ffprobe.get_video_resolution')
    def test_build_crop_filter_invalid_dimensions(self, mock_resolution, tmp_path):
        """Test avec dimensions trop petites après crop."""
        # Crop qui laisse moins que le minimum (640x480)
        settings = Settings(
            crop={'enabled': True, 'bottom': 700, 'right': 1400}  # Crop trop important
        )
        with patch.object(FFmpegCutter, '_validate_ffmpeg'):
            cutter = FFmpegCutter(settings)
        
        mock_resolution.return_value = (1920, 1080)
        source_path = tmp_path / "source.mp4"
        source_path.write_text("fake video")
        
        crop_filter = cutter._build_crop_filter(source_path)
        
        assert crop_filter is None  # Doit retourner None en cas d'erreur
    
    def test_build_ffmpeg_command_with_crop(self, cutter_with_crop, plan_item, tmp_path):
        """Test de construction commande FFmpeg avec crop."""
        source_path = tmp_path / "source.mp4"
        source_path.write_text("fake video")
        
        # Simuler la résolution et le crop filter
        with patch.object(cutter_with_crop, '_build_crop_filter', return_value="crop=1920:1040:0:0"):
            cmd = cutter_with_crop._build_ffmpeg_command(source_path, plan_item)
        
        # Vérifications
        assert "-vf" in cmd
        crop_index = cmd.index("-vf")
        assert cmd[crop_index + 1] == "crop=1920:1040:0:0"
        assert "libx264" in cmd  # S'assurer que les autres options sont toujours là
    
    def test_build_ffmpeg_command_crop_disabled(self, plan_item, tmp_path):
        """Test que la commande ne contient pas -vf quand crop désactivé."""
        settings = Settings(crop={'enabled': False})
        with patch.object(FFmpegCutter, '_validate_ffmpeg'):
            cutter = FFmpegCutter(settings)
        
        source_path = tmp_path / "source.mp4" 
        source_path.write_text("fake video")
        
        cmd = cutter._build_ffmpeg_command(source_path, plan_item)
        
        assert "-vf" not in cmd  # Pas de filtre vidéo
        assert "libx264" in cmd  # Autres options présentes
    
    @patch('ytsplit.utils.ffprobe.get_video_resolution')
    def test_build_crop_filter_resolution_error(self, mock_resolution, cutter_with_crop, tmp_path):
        """Test de gestion d'erreur lors de l'obtention de résolution."""
        from ytsplit.utils.ffprobe import FFprobeError
        mock_resolution.side_effect = FFprobeError("Erreur FFprobe")
        
        source_path = tmp_path / "source.mp4"
        source_path.write_text("fake video")
        
        crop_filter = cutter_with_crop._build_crop_filter(source_path)
        
        assert crop_filter is None  # Doit gérer l'erreur gracieusement


class TestFFmpegGPU:
    """Tests pour les fonctionnalités GPU."""
    
    @pytest.fixture
    def settings_with_gpu(self):
        """Settings avec GPU activé."""
        return Settings(
            gpu={'enabled': True, 'encoder': 'h264_nvenc', 'preset': 'p7', 'cq': 18}
        )
    
    @pytest.fixture
    def cutter_with_gpu(self, settings_with_gpu):
        """Cutter avec GPU activé."""
        with patch.object(FFmpegCutter, '_validate_ffmpeg'):
            return FFmpegCutter(settings_with_gpu)
    
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
    def test_check_nvenc_availability_success(self, mock_run):
        """Test de détection NVENC disponible."""
        from ytsplit.cutting.ffmpeg import check_nvenc_availability
        
        # Simuler ffmpeg avec NVENC disponible
        mock_run.return_value = Mock(
            returncode=0, 
            stdout="V..... h264_nvenc         NVIDIA NVENC H.264 encoder"
        )
        
        result = check_nvenc_availability()
        
        assert result == True
        mock_run.assert_called_once_with([
            "ffmpeg", "-hide_banner", "-encoders"
        ], capture_output=True, text=True, timeout=10)
    
    @patch('subprocess.run')
    def test_check_nvenc_availability_not_found(self, mock_run):
        """Test NVENC non disponible."""
        from ytsplit.cutting.ffmpeg import check_nvenc_availability
        
        # Simuler ffmpeg sans NVENC
        mock_run.return_value = Mock(
            returncode=0,
            stdout="V..... libx264           libx264 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10"
        )
        
        result = check_nvenc_availability()
        
        assert result == False
    
    @patch('subprocess.run')
    def test_check_nvenc_availability_ffmpeg_error(self, mock_run):
        """Test erreur FFmpeg lors de la détection NVENC."""
        from ytsplit.cutting.ffmpeg import check_nvenc_availability
        
        mock_run.return_value = Mock(returncode=1)
        
        result = check_nvenc_availability()
        
        assert result == False
    
    @patch('subprocess.run')
    def test_check_nvenc_availability_timeout(self, mock_run):
        """Test timeout lors de la détection NVENC."""
        from ytsplit.cutting.ffmpeg import check_nvenc_availability
        
        mock_run.side_effect = subprocess.TimeoutExpired("ffmpeg", 10)
        
        result = check_nvenc_availability()
        
        assert result == False
    
    @patch('subprocess.run')
    def test_check_nvenc_availability_file_not_found(self, mock_run):
        """Test FFmpeg non trouvé."""
        from ytsplit.cutting.ffmpeg import check_nvenc_availability
        
        mock_run.side_effect = FileNotFoundError("ffmpeg not found")
        
        result = check_nvenc_availability()
        
        assert result == False
    
    def test_check_gpu_compatibility_disabled(self):
        """Test compatibilité GPU désactivée."""
        from ytsplit.cutting.ffmpeg import check_gpu_compatibility
        
        settings = Settings(gpu={'enabled': False})
        
        is_compatible, message = check_gpu_compatibility(settings)
        
        assert is_compatible == False
        assert "GPU désactivé" in message
    
    @patch('ytsplit.cutting.ffmpeg.check_nvenc_availability')
    def test_check_gpu_compatibility_nvenc_not_available(self, mock_nvenc):
        """Test NVENC non disponible."""
        from ytsplit.cutting.ffmpeg import check_gpu_compatibility
        
        mock_nvenc.return_value = False
        settings = Settings(gpu={'enabled': True})
        
        is_compatible, message = check_gpu_compatibility(settings)
        
        assert is_compatible == False
        assert "NVENC non disponible" in message
    
    @patch('ytsplit.cutting.ffmpeg.check_nvenc_availability')
    def test_check_gpu_compatibility_success(self, mock_nvenc):
        """Test compatibilité GPU réussie."""
        from ytsplit.cutting.ffmpeg import check_gpu_compatibility
        
        mock_nvenc.return_value = True
        settings = Settings(gpu={'enabled': True, 'encoder': 'h264_nvenc', 'preset': 'p7'})
        
        is_compatible, message = check_gpu_compatibility(settings)
        
        assert is_compatible == True
        assert "GPU prêt: h264_nvenc preset p7" in message
    
    @patch('ytsplit.cutting.ffmpeg.check_gpu_compatibility')
    def test_build_ffmpeg_command_with_gpu(self, mock_gpu_check, cutter_with_gpu, plan_item, tmp_path):
        """Test construction commande FFmpeg avec GPU."""
        # Simuler GPU compatible
        mock_gpu_check.return_value = (True, "GPU ready")
        
        source_path = tmp_path / "source.mp4"
        source_path.write_text("fake video")
        
        cmd = cutter_with_gpu._build_ffmpeg_command(source_path, plan_item)
        
        # Vérifications GPU
        assert "-hwaccel" in cmd
        assert "cuda" in cmd
        assert "-c:v" in cmd
        assert "h264_nvenc" in cmd
        assert "-preset" in cmd
        assert "p7" in cmd
        assert "-cq" in cmd
        assert "18" in cmd
        assert "-c:a" in cmd
        assert "copy" in cmd  # Audio en copy pour GPU
    
    @patch('ytsplit.cutting.ffmpeg.check_gpu_compatibility')
    def test_build_ffmpeg_command_gpu_fallback_cpu(self, mock_gpu_check, cutter_with_gpu, plan_item, tmp_path):
        """Test fallback CPU quand GPU non compatible."""
        # Simuler GPU non compatible
        mock_gpu_check.return_value = (False, "GPU not ready")
        
        source_path = tmp_path / "source.mp4"
        source_path.write_text("fake video")
        
        cmd = cutter_with_gpu._build_ffmpeg_command(source_path, plan_item)
        
        # Vérifications fallback CPU
        assert "-hwaccel" not in cmd
        assert "cuda" not in cmd
        assert "-c:v" in cmd
        assert "libx264" in cmd  # Fallback x264
        assert "-crf" in cmd
        assert "-preset" in cmd
        assert "veryfast" in cmd  # Preset x264
        assert "-c:a" in cmd
        assert "aac" in cmd  # Audio réencodé en CPU
    
    @patch('ytsplit.cutting.ffmpeg.check_gpu_compatibility')
    @patch('ytsplit.utils.ffprobe.get_video_resolution')
    def test_build_ffmpeg_command_gpu_with_crop(self, mock_resolution, mock_gpu_check, tmp_path):
        """Test GPU avec crop activé."""
        # Settings avec GPU et crop
        settings = Settings(
            gpu={'enabled': True, 'encoder': 'h264_nvenc', 'preset': 'p7'},
            crop={'enabled': True, 'bottom': 40}
        )
        with patch.object(FFmpegCutter, '_validate_ffmpeg'):
            cutter = FFmpegCutter(settings)
        
        mock_gpu_check.return_value = (True, "GPU ready")
        mock_resolution.return_value = (1920, 1080)
        
        plan_item = SplitPlanItem(
            video_id="test123",
            chapter_index=1, 
            chapter_title="Test Chapter",
            start_s=10.0,
            end_s=70.0,
            expected_duration_s=60.0,
            output_path=tmp_path / "01 - Test Chapter.mp4"
        )
        
        source_path = tmp_path / "source.mp4"
        source_path.write_text("fake video")
        
        cmd = cutter._build_ffmpeg_command(source_path, plan_item)
        
        # Vérifications GPU + crop
        assert "-vf" in cmd
        vf_index = cmd.index("-vf")
        vf_filter = cmd[vf_index + 1]
        assert "hwupload_cuda" in vf_filter
        assert "crop=1920:1040:0:0" in vf_filter
        assert "hwdownload" in vf_filter
        assert "h264_nvenc" in cmd
    
    @patch('ytsplit.cutting.ffmpeg.check_gpu_compatibility')
    @patch('ytsplit.utils.ffprobe.get_video_resolution')
    def test_build_ffmpeg_command_cpu_with_crop(self, mock_resolution, mock_gpu_check, tmp_path):
        """Test CPU avec crop activé."""
        settings = Settings(
            gpu={'enabled': True},  # GPU activé mais pas compatible
            crop={'enabled': True, 'bottom': 40}
        )
        with patch.object(FFmpegCutter, '_validate_ffmpeg'):
            cutter = FFmpegCutter(settings)
        
        mock_gpu_check.return_value = (False, "GPU not ready")
        mock_resolution.return_value = (1920, 1080)
        
        plan_item = SplitPlanItem(
            video_id="test123",
            chapter_index=1,
            chapter_title="Test Chapter", 
            start_s=10.0,
            end_s=70.0,
            expected_duration_s=60.0,
            output_path=tmp_path / "01 - Test Chapter.mp4"
        )
        
        source_path = tmp_path / "source.mp4"
        source_path.write_text("fake video")
        
        cmd = cutter._build_ffmpeg_command(source_path, plan_item)
        
        # Vérifications CPU + crop (pas de hw upload/download)
        assert "-vf" in cmd
        vf_index = cmd.index("-vf")
        vf_filter = cmd[vf_index + 1]
        assert vf_filter == "crop=1920:1040:0:0"  # Crop simple sans GPU
        assert "hwupload_cuda" not in vf_filter
        assert "libx264" in cmd