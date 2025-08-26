"""Tests pour le module de parsing des timecodes."""

import pytest
from ytsplit.parsing.timecode import (
    parse_timecode, 
    seconds_to_timecode, 
    format_duration,
    validate_timecode_range,
    TimecodeError
)


class TestParseTimecode:
    """Tests pour la fonction parse_timecode."""
    
    def test_parse_hms_format(self):
        """Test du format HH:MM:SS."""
        assert parse_timecode("01:23:45") == 5025.0  # 1*3600 + 23*60 + 45
        assert parse_timecode("00:00:00") == 0.0
        assert parse_timecode("12:34:56") == 45296.0
    
    def test_parse_hms_with_milliseconds(self):
        """Test du format HH:MM:SS.mmm."""
        assert parse_timecode("01:23:45.123") == 5025.123
        assert parse_timecode("00:00:01.500") == 1.5
        assert parse_timecode("12:34:56.999") == 45296.999
    
    def test_parse_ms_format(self):
        """Test du format MM:SS."""
        assert parse_timecode("23:45") == 1425.0  # 23*60 + 45
        assert parse_timecode("00:00") == 0.0
        assert parse_timecode("59:59") == 3599.0
    
    def test_parse_ms_with_milliseconds(self):
        """Test du format MM:SS.mmm."""
        assert parse_timecode("23:45.123") == 1425.123
        assert parse_timecode("01:30.500") == 90.5
    
    def test_parse_seconds_only(self):
        """Test du format SS."""
        assert parse_timecode("45") == 45.0
        assert parse_timecode("00") == 0.0
        assert parse_timecode("59") == 59.0
    
    def test_parse_seconds_with_milliseconds(self):
        """Test du format SS.mmm."""
        assert parse_timecode("45.123") == 45.123
        assert parse_timecode("01.500") == 1.5
    
    def test_invalid_formats(self):
        """Test des formats invalides."""
        with pytest.raises(TimecodeError):
            parse_timecode("")
        
        with pytest.raises(TimecodeError):
            parse_timecode("invalid")
        
        with pytest.raises(TimecodeError):
            parse_timecode("1:2:3:4")  # Trop de parties
    
    def test_invalid_values(self):
        """Test des valeurs invalides."""
        with pytest.raises(TimecodeError):
            parse_timecode("00:60:00")  # Minutes >= 60
        
        with pytest.raises(TimecodeError):
            parse_timecode("00:00:60")  # Secondes >= 60
    
    def test_edge_cases(self):
        """Test des cas limites."""
        assert parse_timecode("  01:23:45  ") == 5025.0  # Espaces
        assert parse_timecode("1:2:3") == 3723.0  # Sans zéros de padding


class TestSecondsToTimecode:
    """Tests pour la fonction seconds_to_timecode."""
    
    def test_basic_conversion(self):
        """Test de conversion basique."""
        assert seconds_to_timecode(5025) == "01:23:45"
        assert seconds_to_timecode(0) == "00:00:00"
        assert seconds_to_timecode(3661) == "01:01:01"
    
    def test_with_milliseconds(self):
        """Test avec millisecondes."""
        # Utiliser des valeurs qui n'ont pas de problèmes de précision floating point
        assert seconds_to_timecode(5025.500, include_milliseconds=True) == "01:23:45.500"
        assert seconds_to_timecode(1.5, include_milliseconds=True) == "00:00:01.500"
    
    def test_without_milliseconds(self):
        """Test sans millisecondes."""
        assert seconds_to_timecode(5025.123, include_milliseconds=False) == "01:23:45"
        assert seconds_to_timecode(1.999, include_milliseconds=False) == "00:00:01"
    
    def test_negative_seconds(self):
        """Test avec des secondes négatives."""
        with pytest.raises(TimecodeError):
            seconds_to_timecode(-1)


class TestFormatDuration:
    """Tests pour la fonction format_duration."""
    
    def test_format_duration(self):
        """Test du formatage de durée."""
        assert format_duration(3661) == "1h 1m 1s"
        assert format_duration(125) == "2m 5s"
        assert format_duration(45) == "45s"
        assert format_duration(0) == "0s"
        assert format_duration(3600) == "1h"
        assert format_duration(60) == "1m"


class TestValidateTimecodeRange:
    """Tests pour la fonction validate_timecode_range."""
    
    def test_valid_range(self):
        """Test d'un range valide."""
        assert validate_timecode_range(10.0, 20.0) == True
        assert validate_timecode_range(0.0, 100.0, max_duration_s=200.0) == True
    
    def test_invalid_range(self):
        """Test de ranges invalides."""
        with pytest.raises(TimecodeError):
            validate_timecode_range(20.0, 10.0)  # end <= start
        
        with pytest.raises(TimecodeError):
            validate_timecode_range(-1.0, 10.0)  # start négatif
        
        with pytest.raises(TimecodeError):
            validate_timecode_range(10.0, -1.0)  # end négatif
        
        with pytest.raises(TimecodeError):
            validate_timecode_range(10.0, 150.0, max_duration_s=100.0)  # end > max_duration


class TestRoundTrip:
    """Tests de conversion aller-retour."""
    
    def test_parse_and_format_round_trip(self):
        """Test de conversion aller-retour."""
        test_cases = [
            "01:23:45",
            "00:00:01",
            "12:34:56.123"
        ]
        
        for timecode_str in test_cases:
            seconds = parse_timecode(timecode_str)
            formatted = seconds_to_timecode(seconds, include_milliseconds=True)
            # Re-parser pour vérifier la cohérence
            reparsed = parse_timecode(formatted)
            assert abs(seconds - reparsed) < 0.001  # Tolérance pour les float