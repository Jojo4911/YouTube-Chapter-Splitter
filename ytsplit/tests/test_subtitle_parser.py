"""Tests pour le parser de sous-titres."""

import pytest
from pathlib import Path
import tempfile
from datetime import timedelta

from ..subtitles.parser import SubtitleParser, SubtitleParseError, create_subtitle_parser
from ..subtitles.models import SubtitleFile, SubtitleEntry


class TestSubtitleParser:
    """Tests pour SubtitleParser."""
    
    @pytest.fixture
    def parser(self):
        """Parser par défaut."""
        return SubtitleParser()
    
    @pytest.fixture
    def sample_srt_content(self):
        """Contenu SRT de test."""
        return """1
00:00:01,000 --> 00:00:03,000
Premier sous-titre

2
00:00:05,500 --> 00:00:07,200
Deuxième sous-titre

3
00:01:00,000 --> 00:01:02,500
Troisième sous-titre avec des <b>balises HTML</b>
"""
    
    @pytest.fixture
    def sample_vtt_content(self):
        """Contenu VTT de test."""
        return """WEBVTT

00:00:01.000 --> 00:00:03.000
Premier sous-titre VTT

00:00:05.500 --> 00:00:07.200
Deuxième sous-titre VTT

NOTE
This is a comment

01:00:00.000 --> 01:00:02.500
Troisième sous-titre avec <c>balises</c> WebVTT
"""
    
    def test_detect_srt_format(self, parser):
        """Test détection format SRT."""
        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False) as f:
            file_path = Path(f.name)
        
        try:
            assert parser._detect_format(file_path) == "srt"
        finally:
            file_path.unlink()
    
    def test_detect_vtt_format(self, parser):
        """Test détection format VTT."""
        with tempfile.NamedTemporaryFile(suffix=".vtt", delete=False) as f:
            file_path = Path(f.name)
        
        try:
            assert parser._detect_format(file_path) == "vtt"
        finally:
            file_path.unlink()
    
    def test_detect_unsupported_format(self, parser):
        """Test détection format non supporté."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            file_path = Path(f.name)
        
        try:
            with pytest.raises(SubtitleParseError, match="Extension de fichier non supportée"):
                parser._detect_format(file_path)
        finally:
            file_path.unlink()
    
    def test_extract_language_from_filename(self, parser):
        """Test extraction langue depuis nom de fichier."""
        assert parser._extract_language_from_filename(Path("video.fr.srt")) == "fr"
        assert parser._extract_language_from_filename(Path("video.en.vtt")) == "en"
        assert parser._extract_language_from_filename(Path("video.srt")) is None
        assert parser._extract_language_from_filename(Path("video.123.srt")) is None
    
    def test_parse_srt_content(self, parser, sample_srt_content):
        """Test parsing contenu SRT."""
        entries = parser._parse_srt_content(sample_srt_content)
        
        assert len(entries) == 3
        
        # Premier sous-titre
        assert entries[0].index == 1
        assert entries[0].start_s == 1.0
        assert entries[0].end_s == 3.0
        assert entries[0].content == "Premier sous-titre"
        
        # Deuxième sous-titre
        assert entries[1].index == 2
        assert entries[1].start_s == 5.5
        assert entries[1].end_s == 7.2
        assert entries[1].content == "Deuxième sous-titre"
        
        # Troisième sous-titre (balises HTML supprimées)
        assert entries[2].index == 3
        assert entries[2].start_s == 60.0
        assert entries[2].end_s == 62.5
        assert entries[2].content == "Troisième sous-titre avec des balises HTML"
    
    def test_parse_vtt_content(self, parser, sample_vtt_content):
        """Test parsing contenu VTT."""
        entries = parser._parse_vtt_content(sample_vtt_content)
        
        assert len(entries) == 3
        
        # Premier sous-titre
        assert entries[0].index == 1
        assert entries[0].start_s == 1.0
        assert entries[0].end_s == 3.0
        assert entries[0].content == "Premier sous-titre VTT"
        
        # Deuxième sous-titre
        assert entries[1].index == 2
        assert entries[1].start_s == 5.5
        assert entries[1].end_s == 7.2
        assert entries[1].content == "Deuxième sous-titre VTT"
        
        # Troisième sous-titre (balises WebVTT supprimées)
        assert entries[2].index == 3
        assert entries[2].start_s == 3600.0  # 1 hour
        assert entries[2].end_s == 3602.5
        assert entries[2].content == "Troisième sous-titre avec balises WebVTT"
    
    def test_parse_timestamp_formats(self, parser):
        """Test parsing différents formats de timestamp."""
        assert parser._parse_timestamp("00:00:01.000") == 1.0
        assert parser._parse_timestamp("00:01:30.500") == 90.5
        assert parser._parse_timestamp("01:00:00.000") == 3600.0
        assert parser._parse_timestamp("00:00:01,000") == 1.0  # Virgule décimale
    
    def test_parse_invalid_timestamp(self, parser):
        """Test parsing timestamp invalide."""
        with pytest.raises(SubtitleParseError):
            parser._parse_timestamp("invalid")
        
        with pytest.raises(SubtitleParseError):
            parser._parse_timestamp("25:00:00.000")  # Format invalide
    
    def test_clean_subtitle_content(self, parser):
        """Test nettoyage contenu sous-titre."""
        # Balises HTML
        assert parser._clean_subtitle_content("<b>Gras</b>") == "Gras"
        assert parser._clean_subtitle_content("<i>Italique</i>") == "Italique"
        
        # Balises WebVTT
        assert parser._clean_subtitle_content("<c>Couleur</c>") == "Couleur"
        assert parser._clean_subtitle_content("<v Speaker>Parole</v>") == "Parole"
        
        # Espaces multiples
        assert parser._clean_subtitle_content("Texte   avec    espaces") == "Texte avec espaces"
    
    def test_parse_srt_file(self, parser, sample_srt_content):
        """Test parsing fichier SRT complet."""
        with tempfile.NamedTemporaryFile(mode='w', suffix=".fr.srt", encoding='utf-8', delete=False) as f:
            f.write(sample_srt_content)
            file_path = Path(f.name)
        
        try:
            subtitle_file = parser.parse_file(file_path)
            
            assert subtitle_file.file_path == file_path
            assert subtitle_file.language == "fr"
            assert subtitle_file.format == "srt"
            assert len(subtitle_file.entries) == 3
            assert subtitle_file.encoding == "utf-8"
            
        finally:
            file_path.unlink()
    
    def test_parse_vtt_file(self, parser, sample_vtt_content):
        """Test parsing fichier VTT complet."""
        with tempfile.NamedTemporaryFile(mode='w', suffix=".en.vtt", encoding='utf-8', delete=False) as f:
            f.write(sample_vtt_content)
            file_path = Path(f.name)
        
        try:
            subtitle_file = parser.parse_file(file_path, language="en")
            
            assert subtitle_file.file_path == file_path
            assert subtitle_file.language == "en"  # Explicite
            assert subtitle_file.format == "vtt"
            assert len(subtitle_file.entries) == 3
            
        finally:
            file_path.unlink()
    
    def test_parse_nonexistent_file(self, parser):
        """Test parsing fichier inexistant."""
        with pytest.raises(SubtitleParseError, match="Fichier introuvable"):
            parser.parse_file(Path("nonexistent.srt"))
    
    def test_write_srt_file(self, parser):
        """Test écriture fichier SRT."""
        entries = [
            SubtitleEntry(index=1, start_s=1.0, end_s=3.0, content="Premier"),
            SubtitleEntry(index=2, start_s=5.0, end_s=7.0, content="Deuxième")
        ]
        
        subtitle_file = SubtitleFile(
            file_path=Path("test.srt"),
            format="srt",
            entries=entries,
            encoding="utf-8"
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix=".srt", delete=False) as f:
            output_path = Path(f.name)
        
        try:
            parser.write_srt_file(subtitle_file, output_path)
            
            # Vérifier que le fichier existe et contient le bon contenu
            assert output_path.exists()
            content = output_path.read_text(encoding='utf-8')
            
            assert "1\n00:00:01,000 --> 00:00:03,000\nPremier" in content
            assert "2\n00:00:05,000 --> 00:00:07,000\nDeuxième" in content
            
        finally:
            output_path.unlink()
    
    def test_malformed_srt_content(self, parser):
        """Test contenu SRT malformé."""
        malformed_srt = """1
00:00:01,000 -> 00:00:03,000  # Mauvaise flèche
Premier sous-titre

2
invalid_timestamp --> 00:00:07,000  # Timestamp invalide
Deuxième sous-titre
"""
        
        # Le parser doit être robuste et ignorer les entrées malformées
        entries = parser._parse_srt_content(malformed_srt)
        assert len(entries) == 0  # Aucune entrée valide
    
    def test_factory_function(self):
        """Test fonction factory."""
        parser = create_subtitle_parser("iso-8859-1")
        assert isinstance(parser, SubtitleParser)
        assert parser.encoding == "iso-8859-1"