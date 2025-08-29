"""Tests pour les modèles de sous-titres."""

import pytest
from pathlib import Path
from datetime import timedelta

from ..subtitles.models import SubtitleEntry, SubtitleFile, SubtitleSliceResult


class TestSubtitleEntry:
    """Tests pour SubtitleEntry."""
    
    def test_valid_entry(self):
        """Test création d'une entrée valide."""
        entry = SubtitleEntry(
            index=1,
            start_s=0.5,
            end_s=2.3,
            content="Hello world"
        )
        
        assert entry.index == 1
        assert entry.start_s == 0.5
        assert entry.end_s == 2.3
        assert entry.content == "Hello world"
        assert entry.duration_s == 1.8
    
    def test_timedelta_properties(self):
        """Test propriétés timedelta."""
        entry = SubtitleEntry(
            index=1,
            start_s=60.5,
            end_s=62.3,
            content="Test"
        )
        
        assert entry.start_timedelta == timedelta(seconds=60.5)
        assert entry.end_timedelta == timedelta(seconds=62.3)
    
    def test_invalid_timing(self):
        """Test validation timing invalide."""
        with pytest.raises(ValueError, match="end_s .* doit être supérieur à start_s"):
            SubtitleEntry(
                index=1,
                start_s=2.0,
                end_s=1.0,
                content="Invalid"
            )
    
    def test_equal_timing(self):
        """Test timing égal (invalide)."""
        with pytest.raises(ValueError, match="end_s .* doit être supérieur à start_s"):
            SubtitleEntry(
                index=1,
                start_s=1.0,
                end_s=1.0,
                content="Equal timing"
            )
    
    def test_negative_index(self):
        """Test index négatif (invalide)."""
        with pytest.raises(ValueError):
            SubtitleEntry(
                index=-1,
                start_s=0.0,
                end_s=1.0,
                content="Negative index"
            )
    
    def test_negative_timing(self):
        """Test timing négatif (invalide)."""
        with pytest.raises(ValueError):
            SubtitleEntry(
                index=1,
                start_s=-1.0,
                end_s=1.0,
                content="Negative timing"
            )


class TestSubtitleFile:
    """Tests pour SubtitleFile."""
    
    def test_valid_subtitle_file(self):
        """Test création d'un fichier de sous-titres valide."""
        entries = [
            SubtitleEntry(index=1, start_s=0.0, end_s=2.0, content="First"),
            SubtitleEntry(index=2, start_s=3.0, end_s=5.0, content="Second")
        ]
        
        subtitle_file = SubtitleFile(
            file_path=Path("test.srt"),
            language="fr",
            format="srt",
            entries=entries,
            encoding="utf-8"
        )
        
        assert subtitle_file.file_path == Path("test.srt")
        assert subtitle_file.language == "fr"
        assert subtitle_file.format == "srt"
        assert len(subtitle_file.entries) == 2
        assert subtitle_file.encoding == "utf-8"
    
    def test_total_duration(self):
        """Test calcul durée totale."""
        entries = [
            SubtitleEntry(index=1, start_s=0.0, end_s=2.0, content="First"),
            SubtitleEntry(index=2, start_s=3.0, end_s=7.5, content="Second")
        ]
        
        subtitle_file = SubtitleFile(
            file_path=Path("test.srt"),
            format="srt",
            entries=entries
        )
        
        assert subtitle_file.total_duration_s == 7.5
        assert subtitle_file.entry_count == 2
    
    def test_empty_file(self):
        """Test fichier vide."""
        subtitle_file = SubtitleFile(
            file_path=Path("empty.srt"),
            format="srt",
            entries=[]
        )
        
        assert subtitle_file.total_duration_s == 0.0
        assert subtitle_file.entry_count == 0


class TestSubtitleSliceResult:
    """Tests pour SubtitleSliceResult."""
    
    def test_valid_result(self):
        """Test résultat valide."""
        result = SubtitleSliceResult(
            output_path=Path("output.srt"),
            chapter_index=1,
            chapter_title="Chapter 1",
            start_s=0.0,
            end_s=120.0,
            entry_count=5,
            filtered_count=2,
            status="OK",
            message="Succès"
        )
        
        assert result.output_path == Path("output.srt")
        assert result.chapter_index == 1
        assert result.chapter_title == "Chapter 1"
        assert result.start_s == 0.0
        assert result.end_s == 120.0
        assert result.entry_count == 5
        assert result.filtered_count == 2
        assert result.status == "OK"
        assert result.message == "Succès"
    
    def test_empty_result(self):
        """Test résultat vide."""
        result = SubtitleSliceResult(
            output_path=Path("empty.srt"),
            chapter_index=2,
            chapter_title="Empty Chapter",
            start_s=60.0,
            end_s=180.0,
            entry_count=0,
            status="EMPTY"
        )
        
        assert result.entry_count == 0
        assert result.status == "EMPTY"
        assert result.filtered_count == 0  # Default value
    
    def test_error_result(self):
        """Test résultat d'erreur."""
        result = SubtitleSliceResult(
            output_path=Path("error.srt"),
            chapter_index=3,
            chapter_title="Error Chapter",
            start_s=120.0,
            end_s=240.0,
            entry_count=0,
            status="ERROR",
            message="Erreur de traitement"
        )
        
        assert result.status == "ERROR"
        assert result.message == "Erreur de traitement"