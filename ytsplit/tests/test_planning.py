"""Tests pour le module de planification."""

import pytest
from pathlib import Path
from unittest.mock import patch

from ytsplit.planning.plan import SplitPlanner, PlanningError, create_split_planner
from ytsplit.config import Settings
from ytsplit.models import VideoMeta, Chapter, SplitPlanItem


class TestSplitPlanner:
    """Tests pour la classe SplitPlanner."""
    
    @pytest.fixture
    def settings(self):
        """Settings de test."""
        return Settings(
            out_dir=Path("./test_output"),
            video_format="mp4",
            naming={
                'template': '{n:02d} - {title}',
                'sanitize_maxlen': 100,
                'replace_chars': {'<': '＜', '>': '＞', ':': '：'}
            }
        )
    
    @pytest.fixture
    def planner(self, settings):
        """SplitPlanner de test."""
        return SplitPlanner(settings)
    
    @pytest.fixture
    def video_meta(self):
        """Métadonnées vidéo de test."""
        chapters = [
            Chapter(index=1, title="Introduction", start_s=0.0, end_s=60.0),
            Chapter(index=2, title="Main Content", start_s=60.0, end_s=180.0),
            Chapter(index=3, title="Conclusion", start_s=180.0, end_s=240.0)
        ]
        
        return VideoMeta(
            video_id="test123",
            title="Test Video",
            duration_s=240.0,
            chapters=chapters,
            url="https://youtube.com/watch?v=test123"
        )
    
    def test_build_split_plan_success(self, planner, video_meta):
        """Test de génération de plan réussie."""
        plan = planner.build_split_plan(video_meta)
        
        # Vérifications de base
        assert len(plan) == 3
        assert all(isinstance(item, SplitPlanItem) for item in plan)
        
        # Vérifier le premier item
        first_item = plan[0]
        assert first_item.video_id == "test123"
        assert first_item.chapter_index == 1
        assert first_item.chapter_title == "Introduction"
        assert first_item.start_s == 0.0
        assert first_item.end_s == 60.0
        assert first_item.expected_duration_s == 60.0
        assert first_item.mode == "reencode"
        
        # Vérifier le nom du fichier de sortie
        assert first_item.output_path.name == "01 - Introduction.mp4"
        assert "Test Video-test123" in str(first_item.output_path.parent)
    
    def test_build_split_plan_no_chapters(self, planner):
        """Test avec vidéo sans chapitres (ne peut pas être créée par Pydantic)."""
        # Simuler une vidéo sans chapitres en contournant la validation
        from ytsplit.models import VideoMeta
        
        # Le test vérifie que le planner détecte cette condition
        # En réalité, VideoMeta ne peut pas être créé sans chapitres grâce à Pydantic
        # Donc on teste directement la méthode avec une liste vide
        
        # Créer une meta normale puis vider la liste
        chapters = [Chapter(index=1, title="Temp", start_s=0.0, end_s=60.0)]
        video_meta = VideoMeta(
            video_id="test123",
            title="Empty Video",
            duration_s=120.0,
            chapters=chapters,
            url="https://youtube.com/watch?v=test123"
        )
        
        # Vider les chapitres après création
        video_meta.chapters = []
        
        with pytest.raises(PlanningError, match="Aucun chapitre à planifier"):
            planner.build_split_plan(video_meta)
    
    def test_build_split_plan_invalid_duration(self, planner):
        """Test avec chapitre de durée invalide (détecté par Pydantic)."""
        # Pydantic empêche la création de chapitres avec end_s <= start_s
        # Donc on teste que Pydantic lève bien l'erreur
        
        with pytest.raises(ValueError):  # ValidationError de Pydantic
            Chapter(index=1, title="Bad Chapter", start_s=100.0, end_s=50.0)
    
    def test_sanitize_video_title(self, planner):
        """Test de sanitisation du titre vidéo."""
        # Titre avec caractères problématiques
        title = 'Test Video: "Special" <Content>'
        video_id = "abc123"
        
        result = planner._sanitize_video_title(title, video_id)
        
        # Vérifier que les caractères problématiques sont remplacés
        assert "：" in result  # : remplacé
        assert "＜" in result  # < remplacé
        assert "＞" in result  # > remplacé
        # Note: " n'est pas dans les replace_chars par défaut du settings de test
        assert result.endswith("-abc123")
    
    def test_generate_chapter_filename(self, planner):
        """Test de génération de nom de fichier."""
        chapter = Chapter(
            index=5,
            title="Advanced Topics",
            start_s=300.0,
            end_s=450.0
        )
        
        filename = planner._generate_chapter_filename(chapter)
        
        assert filename == "05 - Advanced Topics.mp4"
    
    def test_generate_chapter_filename_special_chars(self, planner):
        """Test avec titre contenant des caractères spéciaux."""
        chapter = Chapter(
            index=1,
            title='Chapter: "Special" Content',
            start_s=0.0,
            end_s=60.0
        )
        
        filename = planner._generate_chapter_filename(chapter)
        
        # Vérifier que les caractères spéciaux sont remplacés
        assert "：" in filename
        # Note: " n'est pas dans les replace_chars par défaut du settings de test
        assert filename.endswith(".mp4")
    
    def test_validate_plan_success(self, planner, video_meta):
        """Test de validation de plan valide."""
        plan = planner.build_split_plan(video_meta)
        
        # Ne doit pas lever d'exception
        planner._validate_plan(plan, video_meta.duration_s)
    
    def test_validate_plan_empty(self, planner):
        """Test avec plan vide."""
        with pytest.raises(PlanningError, match="Plan vide"):
            planner._validate_plan([], 120.0)
    
    def test_validate_plan_negative_start(self, planner, tmp_path):
        """Test avec start_s négatif (détecté par Pydantic)."""
        # Pydantic empêche la création de SplitPlanItem avec start_s négatif
        # Testons que Pydantic lève bien l'erreur
        
        with pytest.raises(ValueError):  # ValidationError de Pydantic
            SplitPlanItem(
                video_id="test",
                chapter_index=1,
                chapter_title="Bad Chapter",
                start_s=-10.0,  # Négatif
                end_s=50.0,
                expected_duration_s=60.0,
                output_path=tmp_path / "test.mp4"
            )
    
    def test_validate_plan_exceeds_duration(self, planner, tmp_path):
        """Test avec end_s dépassant la durée vidéo."""
        plan_item = SplitPlanItem(
            video_id="test",
            chapter_index=1,
            chapter_title="Long Chapter",
            start_s=0.0,
            end_s=150.0,  # Dépasse les 120s de vidéo
            expected_duration_s=150.0,
            output_path=tmp_path / "test.mp4"
        )
        
        with pytest.raises(PlanningError, match="dépasse la durée vidéo"):
            planner._validate_plan([plan_item], 120.0)
    
    def test_validate_plan_overlapping_chapters(self, planner, tmp_path):
        """Test avec chapitres qui se chevauchent."""
        plan_items = [
            SplitPlanItem(
                video_id="test",
                chapter_index=1,
                chapter_title="Chapter 1",
                start_s=0.0,
                end_s=70.0,  # Se chevauche avec le suivant
                expected_duration_s=70.0,
                output_path=tmp_path / "ch1.mp4"
            ),
            SplitPlanItem(
                video_id="test",
                chapter_index=2,
                chapter_title="Chapter 2",
                start_s=60.0,  # Commence avant la fin du précédent
                end_s=120.0,
                expected_duration_s=60.0,
                output_path=tmp_path / "ch2.mp4"
            )
        ]
        
        with pytest.raises(PlanningError, match="Chevauchement détecté"):
            planner._validate_plan(plan_items, 120.0)
    
    def test_validate_plan_duplicate_filenames(self, planner, tmp_path):
        """Test avec noms de fichiers en doublon."""
        same_output_path = tmp_path / "duplicate.mp4"
        
        plan_items = [
            SplitPlanItem(
                video_id="test",
                chapter_index=1,
                chapter_title="Chapter 1",
                start_s=0.0,
                end_s=60.0,
                expected_duration_s=60.0,
                output_path=same_output_path
            ),
            SplitPlanItem(
                video_id="test",
                chapter_index=2,
                chapter_title="Chapter 2",
                start_s=60.0,
                end_s=120.0,
                expected_duration_s=60.0,
                output_path=same_output_path  # Même nom !
            )
        ]
        
        with pytest.raises(PlanningError, match="Noms de fichiers en doublon"):
            planner._validate_plan(plan_items, 120.0)
    
    @patch('ytsplit.utils.ffprobe.get_video_duration')
    def test_filter_existing_files(self, mock_duration, planner, video_meta, tmp_path):
        """Test de filtrage des fichiers existants."""
        plan = planner.build_split_plan(video_meta, output_dir=tmp_path)
        
        # Créer un fichier existant valide
        existing_file = plan[0].output_path
        existing_file.parent.mkdir(parents=True, exist_ok=True)
        existing_file.write_text("existing content")
        mock_duration.return_value = 59.9  # Dans la tolérance
        
        to_process, existing = planner.filter_existing_files(plan)
        
        assert len(to_process) == 2  # 2 restants à traiter
        assert len(existing) == 1   # 1 existant valide
        assert existing[0].output_path == existing_file
    
    def test_estimate_processing_time(self, planner, video_meta):
        """Test d'estimation du temps de traitement."""
        plan = planner.build_split_plan(video_meta)
        
        estimates = planner.estimate_processing_time(plan)
        
        # Vérifications de base
        assert "total_video_duration" in estimates
        assert "estimated_processing_time" in estimates
        assert "preset_used" in estimates
        assert "parallel_workers" in estimates
        assert "chapters_count" in estimates
        
        assert estimates["total_video_duration"] == 240.0  # 4 minutes de vidéo
        assert estimates["chapters_count"] == 3
        assert estimates["estimated_processing_time"] > 0


class TestCreateSplitPlanner:
    """Tests pour la factory function."""
    
    def test_create_planner_with_settings(self):
        """Test de création avec settings personnalisés."""
        settings = Settings(out_dir=Path("custom"))
        planner = create_split_planner(settings)
        
        assert isinstance(planner, SplitPlanner)
        assert planner.settings.out_dir == Path("custom")
    
    def test_create_planner_default_settings(self):
        """Test de création avec settings par défaut."""
        planner = create_split_planner()
        
        assert isinstance(planner, SplitPlanner)
        assert planner.settings.out_dir == Path("./output")