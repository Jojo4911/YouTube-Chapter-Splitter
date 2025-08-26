"""Tests pour les modèles Pydantic."""

import pytest
from pathlib import Path
from ytsplit.models import Chapter, VideoMeta, SplitPlanItem, SplitResult, ProcessingStats


class TestChapter:
    """Tests pour le modèle Chapter."""
    
    def test_valid_chapter(self):
        """Test d'un chapitre valide."""
        chapter = Chapter(
            index=1,
            title="Introduction",
            start_s=0.0,
            end_s=120.0,
            raw_label="00:00 Introduction"
        )
        assert chapter.index == 1
        assert chapter.title == "Introduction"
        assert chapter.start_s == 0.0
        assert chapter.end_s == 120.0
    
    def test_invalid_chapter_time_range(self):
        """Test d'un chapitre avec range temporel invalide."""
        with pytest.raises(ValueError, match="end_s.*doit être supérieur.*start_s"):
            Chapter(
                index=1,
                title="Test",
                start_s=120.0,
                end_s=60.0  # end_s < start_s
            )


class TestVideoMeta:
    """Tests pour le modèle VideoMeta."""
    
    def test_valid_video_meta(self):
        """Test de métadonnées vidéo valides."""
        chapters = [
            Chapter(index=1, title="Intro", start_s=0.0, end_s=60.0),
            Chapter(index=2, title="Main", start_s=60.0, end_s=180.0),
        ]
        
        video = VideoMeta(
            video_id="test123",
            title="Test Video",
            duration_s=180.0,
            chapters=chapters,
            url="https://youtube.com/watch?v=test123"
        )
        
        assert video.video_id == "test123"
        assert len(video.chapters) == 2
    
    def test_empty_chapters(self):
        """Test avec liste de chapitres vide."""
        with pytest.raises(ValueError, match="Une vidéo doit avoir au moins un chapitre"):
            VideoMeta(
                video_id="test123",
                title="Test Video",
                duration_s=180.0,
                chapters=[],
                url="https://youtube.com/watch?v=test123"
            )
    
    def test_chapter_sorting(self):
        """Test du tri automatique des chapitres."""
        chapters = [
            Chapter(index=2, title="Second", start_s=60.0, end_s=120.0),
            Chapter(index=1, title="First", start_s=0.0, end_s=60.0),
            Chapter(index=3, title="Third", start_s=120.0, end_s=180.0),
        ]
        
        video = VideoMeta(
            video_id="test123",
            title="Test Video",
            duration_s=180.0,
            chapters=chapters,
            url="https://youtube.com/watch?v=test123"
        )
        
        # Vérifier que les chapitres sont triés par start_s
        assert video.chapters[0].title == "First"
        assert video.chapters[1].title == "Second"
        assert video.chapters[2].title == "Third"
    
    def test_overlapping_chapters(self):
        """Test de détection de chapitres qui se chevauchent."""
        chapters = [
            Chapter(index=1, title="First", start_s=0.0, end_s=90.0),  # Se chevauche avec le suivant
            Chapter(index=2, title="Second", start_s=60.0, end_s=120.0),
        ]
        
        with pytest.raises(ValueError, match="Chevauchement détecté"):
            VideoMeta(
                video_id="test123",
                title="Test Video",
                duration_s=180.0,
                chapters=chapters,
                url="https://youtube.com/watch?v=test123"
            )


class TestSplitPlanItem:
    """Tests pour le modèle SplitPlanItem."""
    
    def test_valid_split_plan_item(self):
        """Test d'un item de plan valide."""
        item = SplitPlanItem(
            video_id="test123",
            chapter_index=1,
            chapter_title="Introduction",
            start_s=0.0,
            end_s=120.0,
            expected_duration_s=120.0,
            output_path=Path("output/01 - Introduction.mp4")
        )
        
        assert item.chapter_index == 1
        assert item.expected_duration_s == 120.0
    
    def test_duration_mismatch(self):
        """Test de détection d'incohérence de durée."""
        with pytest.raises(ValueError, match="expected_duration_s.*ne correspond pas"):
            SplitPlanItem(
                video_id="test123",
                chapter_index=1,
                chapter_title="Test",
                start_s=0.0,
                end_s=120.0,
                expected_duration_s=100.0,  # Incohérent avec end_s - start_s
                output_path=Path("output/test.mp4")
            )


class TestSplitResult:
    """Tests pour le modèle SplitResult."""
    
    def test_valid_split_result(self):
        """Test d'un résultat de découpage valide."""
        result = SplitResult(
            output_path=Path("output/01 - Introduction.mp4"),
            chapter_index=1,
            chapter_title="Introduction",
            start_s=0.0,
            end_s=120.0,
            expected_duration_s=120.0,
            obtained_duration_s=119.8,
            status="OK",
            processing_time_s=45.2
        )
        
        assert result.status == "OK"
        assert result.duration_error_s == pytest.approx(0.2)
        assert result.is_duration_valid(tolerance_s=0.5) == True
        assert result.is_duration_valid(tolerance_s=0.1) == False
    
    def test_duration_properties(self):
        """Test des propriétés de durée."""
        result = SplitResult(
            output_path=Path("test.mp4"),
            chapter_index=1,
            chapter_title="Test",
            start_s=0.0,
            end_s=120.0,
            expected_duration_s=120.0,
            obtained_duration_s=None,  # Pas encore mesuré
            status="ERR"
        )
        
        assert result.duration_error_s is None
        assert result.is_duration_valid() is None


class TestProcessingStats:
    """Tests pour le modèle ProcessingStats."""
    
    def test_valid_processing_stats(self):
        """Test de statistiques valides."""
        stats = ProcessingStats(
            total_chapters=10,
            successful_chapters=8,
            failed_chapters=2,
            total_duration_s=3600.0,
            total_processing_time_s=300.0
        )
        
        assert stats.success_rate == 80.0
        assert stats.total_chapters == 10
    
    def test_chapter_count_validation(self):
        """Test de validation des compteurs de chapitres."""
        with pytest.raises(ValueError, match="successful_chapters.*failed_chapters.*total_chapters"):
            ProcessingStats(
                total_chapters=10,
                successful_chapters=6,
                failed_chapters=3,  # 6 + 3 != 10
                total_duration_s=3600.0,
                total_processing_time_s=300.0
            )
    
    def test_success_rate_edge_cases(self):
        """Test du calcul du taux de réussite dans les cas limites."""
        # Cas où total_chapters = 0
        stats = ProcessingStats(
            total_chapters=0,
            successful_chapters=0,
            failed_chapters=0,
            total_duration_s=0.0,
            total_processing_time_s=0.0
        )
        assert stats.success_rate == 0.0
        
        # Cas 100% de réussite
        stats = ProcessingStats(
            total_chapters=5,
            successful_chapters=5,
            failed_chapters=0,
            total_duration_s=1800.0,
            total_processing_time_s=120.0
        )
        assert stats.success_rate == 100.0