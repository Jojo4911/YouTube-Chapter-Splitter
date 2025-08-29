"""Tests pour le slicer de sous-titres."""

import pytest
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

from ..models import Chapter
from ..config import SubtitleSettings
from ..subtitles.models import SubtitleEntry, SubtitleFile, SubtitleSliceResult
from ..subtitles.slicer import SubtitleSlicer, create_subtitle_slicer
from ..subtitles.parser import SubtitleParser


class TestSubtitleSlicer:
    """Tests pour SubtitleSlicer."""
    
    @pytest.fixture
    def subtitle_settings(self):
        """Configuration de sous-titres par défaut."""
        return SubtitleSettings(
            enabled=True,
            offset_s=0.0,
            min_duration_ms=300,
            encoding="utf-8"
        )
    
    @pytest.fixture
    def mock_parser(self):
        """Parser mocké."""
        return Mock(spec=SubtitleParser)
    
    @pytest.fixture
    def slicer(self, subtitle_settings, mock_parser):
        """Slicer avec parser mocké."""
        return SubtitleSlicer(subtitle_settings, mock_parser)
    
    @pytest.fixture
    def sample_entries(self):
        """Entrées de sous-titres de test."""
        return [
            SubtitleEntry(index=1, start_s=5.0, end_s=8.0, content="Premier sous-titre"),
            SubtitleEntry(index=2, start_s=12.0, end_s=15.0, content="Deuxième sous-titre"),
            SubtitleEntry(index=3, start_s=25.0, end_s=28.0, content="Troisième sous-titre"),
            SubtitleEntry(index=4, start_s=35.0, end_s=38.0, content="Quatrième sous-titre"),
            SubtitleEntry(index=5, start_s=45.0, end_s=48.0, content="Cinquième sous-titre"),
        ]
    
    @pytest.fixture
    def sample_chapters(self):
        """Chapitres de test."""
        return [
            Chapter(index=1, title="Introduction", start_s=0.0, end_s=20.0),
            Chapter(index=2, title="Corps principal", start_s=20.0, end_s=40.0),
            Chapter(index=3, title="Conclusion", start_s=40.0, end_s=50.0),
        ]
    
    @pytest.fixture
    def sample_subtitle_file(self, sample_entries):
        """Fichier de sous-titres de test."""
        return SubtitleFile(
            file_path=Path("test.srt"),
            language="fr",
            format="srt",
            entries=sample_entries,
            encoding="utf-8"
        )
    
    def test_apply_no_offset(self, slicer, sample_entries):
        """Test pas d'offset appliqué."""
        adjusted = slicer._apply_offset(sample_entries, 0.0)
        
        assert len(adjusted) == len(sample_entries)
        for original, adjusted_entry in zip(sample_entries, adjusted):
            assert adjusted_entry.start_s == original.start_s
            assert adjusted_entry.end_s == original.end_s
    
    def test_apply_positive_offset(self, slicer, sample_entries):
        """Test offset positif."""
        adjusted = slicer._apply_offset(sample_entries, 2.0)
        
        assert len(adjusted) == len(sample_entries)
        for original, adjusted_entry in zip(sample_entries, adjusted):
            assert adjusted_entry.start_s == original.start_s + 2.0
            assert adjusted_entry.end_s == original.end_s + 2.0
    
    def test_apply_negative_offset(self, slicer, sample_entries):
        """Test offset négatif."""
        adjusted = slicer._apply_offset(sample_entries, -3.0)
        
        assert len(adjusted) == len(sample_entries)
        
        # Premier sous-titre : 5-3=2.0, 8-3=5.0
        assert adjusted[0].start_s == 2.0
        assert adjusted[0].end_s == 5.0
        
        # Deuxième sous-titre : 12-3=9.0, 15-3=12.0
        assert adjusted[1].start_s == 9.0
        assert adjusted[1].end_s == 12.0
    
    def test_apply_negative_offset_clipping(self, slicer):
        """Test offset négatif avec clipping à 0."""
        entries = [SubtitleEntry(index=1, start_s=1.0, end_s=3.0, content="Test")]
        adjusted = slicer._apply_offset(entries, -2.0)
        
        # 1-2 = -1 -> clippé à 0, 3-2 = 1
        assert adjusted[0].start_s == 0.0
        assert adjusted[0].end_s == 1.0
    
    def test_extract_chapter_subtitles_complete_overlap(self, slicer, sample_entries):
        """Test extraction avec chevauchement complet."""
        chapter = Chapter(index=1, title="Test", start_s=10.0, end_s=30.0)
        result = slicer._extract_chapter_subtitles(sample_entries, chapter)
        
        # Deuxième (12-15) et troisième (25-28) sous-titres sont dans [10, 30]
        assert len(result) == 2
        
        # Premier sous-titre extrait (index 2 -> rebased à 1)
        assert result[0].index == 1
        assert result[0].start_s == 2.0  # 12 - 10
        assert result[0].end_s == 5.0    # 15 - 10
        assert result[0].content == "Deuxième sous-titre"
        
        # Deuxième sous-titre extrait (index 3 -> rebased à 2)
        assert result[1].index == 2
        assert result[1].start_s == 15.0  # 25 - 10
        assert result[1].end_s == 18.0   # 28 - 10
        assert result[1].content == "Troisième sous-titre"
    
    def test_extract_chapter_subtitles_partial_overlap(self, slicer):
        """Test extraction avec chevauchement partiel."""
        entries = [
            SubtitleEntry(index=1, start_s=5.0, end_s=15.0, content="Chevauchement début"),
            SubtitleEntry(index=2, start_s=25.0, end_s=35.0, content="Chevauchement fin"),
        ]
        
        chapter = Chapter(index=1, title="Test", start_s=10.0, end_s=30.0)
        result = slicer._extract_chapter_subtitles(entries, chapter)
        
        assert len(result) == 2
        
        # Premier sous-titre : tronqué de [5,15] à [10,15], rebased à [0,5]
        assert result[0].start_s == 0.0
        assert result[0].end_s == 5.0
        
        # Deuxième sous-titre : tronqué de [25,35] à [25,30], rebased à [15,20]
        assert result[1].start_s == 15.0
        assert result[1].end_s == 20.0
    
    def test_extract_chapter_subtitles_no_overlap(self, slicer):
        """Test extraction sans chevauchement."""
        entries = [
            SubtitleEntry(index=1, start_s=5.0, end_s=8.0, content="Avant chapitre"),
            SubtitleEntry(index=2, start_s=35.0, end_s=38.0, content="Après chapitre"),
        ]
        
        chapter = Chapter(index=1, title="Test", start_s=10.0, end_s=30.0)
        result = slicer._extract_chapter_subtitles(entries, chapter)
        
        assert len(result) == 0
    
    def test_extract_chapter_subtitles_min_duration_filter(self, slicer):
        """Test filtrage durée minimale."""
        # Sous-titre très court qui sera filtré
        entries = [
            SubtitleEntry(index=1, start_s=10.1, end_s=10.2, content="Très court"),  # 0.1s
            SubtitleEntry(index=2, start_s=15.0, end_s=18.0, content="Normal"),      # 3s
        ]
        
        chapter = Chapter(index=1, title="Test", start_s=10.0, end_s=20.0)
        result = slicer._extract_chapter_subtitles(entries, chapter)
        
        # Seul le sous-titre "Normal" doit être conservé
        assert len(result) == 1
        assert result[0].content == "Normal"
        assert result[0].start_s == 5.0  # 15 - 10
        assert result[0].end_s == 8.0    # 18 - 10
    
    def test_extract_chapter_subtitles_min_duration_extension(self, slicer):
        """Test extension à la durée minimale."""
        # Sous-titre court mais extensible
        entries = [
            SubtitleEntry(index=1, start_s=10.1, end_s=10.2, content="Court mais extensible"),
        ]
        
        chapter = Chapter(index=1, title="Test", start_s=10.0, end_s=20.0)
        result = slicer._extract_chapter_subtitles(entries, chapter)
        
        assert len(result) == 1
        assert result[0].start_s == 0.1   # 10.1 - 10
        assert result[0].end_s == 0.4     # Étendu à 300ms (0.3s) + start = 0.4
    
    def test_slice_chapter_success(self, slicer, sample_subtitle_file, sample_chapters, mock_parser):
        """Test découpage d'un chapitre avec succès."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            # Configuration du parser mocké
            mock_parser.write_srt_file.return_value = None
            
            result = slicer._slice_chapter(
                sample_subtitle_file.entries,
                sample_chapters[0],  # Introduction : 0-20s
                output_dir,
                "{n:02d} - {title}"
            )
            
            assert result.status == "OK"
            assert result.chapter_index == 1
            assert result.chapter_title == "Introduction"
            assert result.start_s == 0.0
            assert result.end_s == 20.0
            assert result.entry_count == 2  # Premier (5-8) et deuxième (12-15) sous-titres
            
            # Vérifier que write_srt_file a été appelé
            mock_parser.write_srt_file.assert_called_once()
    
    def test_slice_chapter_empty(self, slicer, sample_chapters):
        """Test découpage chapitre sans sous-titre."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            # Pas d'entrées de sous-titres
            result = slicer._slice_chapter(
                [],
                sample_chapters[0],
                output_dir,
                "{n:02d} - {title}"
            )
            
            assert result.status == "EMPTY"
            assert result.entry_count == 0
            assert "Aucun sous-titre" in result.message
    
    @patch('pathlib.Path.write_text')
    def test_slice_chapter_error(self, mock_write, slicer, sample_subtitle_file, sample_chapters, mock_parser):
        """Test erreur lors du découpage."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            # Simuler une erreur lors de l'écriture
            mock_parser.write_srt_file.side_effect = Exception("Erreur d'écriture")
            
            result = slicer._slice_chapter(
                sample_subtitle_file.entries,
                sample_chapters[0],
                output_dir,
                "{n:02d} - {title}"
            )
            
            assert result.status == "ERROR"
            assert "Erreur lors de la création" in result.message
    
    def test_slice_subtitles_complete(self, slicer, sample_subtitle_file, sample_chapters, mock_parser):
        """Test découpage complet de tous les chapitres."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            mock_parser.write_srt_file.return_value = None
            
            results = slicer.slice_subtitles(
                sample_subtitle_file,
                sample_chapters,
                output_dir,
                "{n:02d} - {title}"
            )
            
            assert len(results) == 3  # 3 chapitres
            
            # Vérifier le premier chapitre
            assert results[0].chapter_index == 1
            assert results[0].status in ["OK", "EMPTY"]
            
            # Vérifier que tous les chapitres ont été traités
            chapter_indices = [r.chapter_index for r in results]
            assert chapter_indices == [1, 2, 3]
    
    def test_slice_from_file(self, slicer, sample_chapters, mock_parser):
        """Test découpage depuis fichier."""
        with tempfile.NamedTemporaryFile(mode='w', suffix=".srt", encoding='utf-8', delete=False) as f:
            f.write("1\n00:00:01,000 --> 00:00:03,000\nTest subtitle\n")
            file_path = Path(f.name)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            # Configuration du parser mocké
            mock_subtitle_file = SubtitleFile(
                file_path=file_path,
                format="srt",
                entries=[SubtitleEntry(index=1, start_s=1.0, end_s=3.0, content="Test subtitle")],
                encoding="utf-8"
            )
            mock_parser.parse_file.return_value = mock_subtitle_file
            mock_parser.write_srt_file.return_value = None
            
            try:
                results = slicer.slice_from_file(
                    file_path,
                    sample_chapters,
                    output_dir,
                    "{n:02d} - {title}"
                )
                
                assert len(results) == 3
                mock_parser.parse_file.assert_called_once_with(file_path)
                
            finally:
                file_path.unlink()
    
    def test_factory_function(self, subtitle_settings):
        """Test fonction factory."""
        slicer = create_subtitle_slicer(subtitle_settings)
        assert isinstance(slicer, SubtitleSlicer)
        assert slicer.settings == subtitle_settings


class TestSubtitleSlicerEdgeCases:
    """Tests pour les cas limites du slicer."""
    
    @pytest.fixture
    def minimal_settings(self):
        """Configuration minimale."""
        return SubtitleSettings(
            enabled=True,
            min_duration_ms=100,  # Très courte durée minimale
            encoding="utf-8"
        )
    
    def test_very_short_chapter(self, minimal_settings):
        """Test chapitre très court."""
        slicer = SubtitleSlicer(minimal_settings)
        
        entries = [SubtitleEntry(index=1, start_s=10.0, end_s=15.0, content="Long subtitle")]
        chapter = Chapter(index=1, title="Short", start_s=12.0, end_s=12.5)  # 0.5s seulement
        
        result = slicer._extract_chapter_subtitles(entries, chapter)
        
        # Le sous-titre doit être tronqué mais conservé
        assert len(result) == 1
        assert result[0].start_s == 0.0     # 12 - 12
        assert result[0].end_s == 0.5       # 12.5 - 12
    
    def test_overlapping_subtitles(self, minimal_settings):
        """Test sous-titres qui se chevauchent."""
        slicer = SubtitleSlicer(minimal_settings)
        
        entries = [
            SubtitleEntry(index=1, start_s=10.0, end_s=15.0, content="Premier"),
            SubtitleEntry(index=2, start_s=12.0, end_s=17.0, content="Deuxième (chevauchant)"),
        ]
        chapter = Chapter(index=1, title="Test", start_s=11.0, end_s=16.0)
        
        result = slicer._extract_chapter_subtitles(entries, chapter)
        
        # Les deux sous-titres doivent être conservés et rebasés
        assert len(result) == 2
        assert result[0].start_s == 0.0   # max(10, 11) - 11 = 0
        assert result[0].end_s == 4.0     # min(15, 16) - 11 = 4
        assert result[1].start_s == 1.0   # max(12, 11) - 11 = 1
        assert result[1].end_s == 5.0     # min(17, 16) - 11 = 5