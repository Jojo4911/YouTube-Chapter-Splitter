"""Utilitaires pour le parsing et la manipulation des timecodes."""

import re
from typing import Union


class TimecodeError(ValueError):
    """Exception levée lors d'erreurs de parsing de timecode."""
    pass


def parse_timecode(timecode_str: str) -> float:
    """
    Convertit un timecode string en secondes float.
    
    Formats supportés:
    - "HH:MM:SS" (ex: "01:23:45")
    - "HH:MM:SS.mmm" (ex: "01:23:45.123")
    - "MM:SS" (ex: "23:45")
    - "MM:SS.mmm" (ex: "23:45.123")
    - "SS" ou "SS.mmm" (ex: "45" ou "45.123")
    
    Args:
        timecode_str: String représentant le timecode
        
    Returns:
        float: Nombre de secondes depuis le début
        
    Raises:
        TimecodeError: Si le format n'est pas reconnu ou invalide
    """
    if not isinstance(timecode_str, str):
        raise TimecodeError(f"Le timecode doit être un string, reçu {type(timecode_str)}")
    
    # Nettoyer la chaîne
    timecode_str = timecode_str.strip()
    
    if not timecode_str:
        raise TimecodeError("Timecode vide")
    
    # Patterns regex pour différents formats
    patterns = [
        # HH:MM:SS.mmm ou HH:MM:SS
        r'^(?P<hours>\d{1,2}):(?P<minutes>\d{1,2}):(?P<seconds>\d{1,2})(?:\.(?P<milliseconds>\d{1,3}))?$',
        # MM:SS.mmm ou MM:SS
        r'^(?P<minutes>\d{1,2}):(?P<seconds>\d{1,2})(?:\.(?P<milliseconds>\d{1,3}))?$',
        # SS.mmm ou SS
        r'^(?P<seconds>\d{1,2})(?:\.(?P<milliseconds>\d{1,3}))?$'
    ]
    
    for pattern in patterns:
        match = re.match(pattern, timecode_str)
        if match:
            groups = match.groupdict()
            
            # Extraire les valeurs avec des défauts
            hours = int(groups.get('hours', 0))
            minutes = int(groups.get('minutes', 0))
            seconds = int(groups.get('seconds', 0))
            
            # Gérer les millisecondes
            milliseconds_str = groups.get('milliseconds', '0')
            if milliseconds_str:
                # Padding à droite pour avoir exactement 3 chiffres
                milliseconds_str = milliseconds_str.ljust(3, '0')[:3]
                milliseconds = int(milliseconds_str)
            else:
                milliseconds = 0
            
            # Validation des valeurs
            if minutes >= 60:
                raise TimecodeError(f"Minutes invalides: {minutes} (doit être < 60)")
            if seconds >= 60:
                raise TimecodeError(f"Secondes invalides: {seconds} (doit être < 60)")
            if milliseconds >= 1000:
                raise TimecodeError(f"Millisecondes invalides: {milliseconds} (doit être < 1000)")
            
            # Calcul du total en secondes
            total_seconds = (hours * 3600) + (minutes * 60) + seconds + (milliseconds / 1000.0)
            
            return total_seconds
    
    raise TimecodeError(f"Format de timecode non reconnu: '{timecode_str}'")


def seconds_to_timecode(seconds: Union[int, float], include_milliseconds: bool = True) -> str:
    """
    Convertit des secondes en string timecode.
    
    Args:
        seconds: Nombre de secondes (peut être float pour inclure les millisecondes)
        include_milliseconds: Si True, inclut les millisecondes dans le format de sortie
        
    Returns:
        str: Timecode au format "HH:MM:SS" ou "HH:MM:SS.mmm"
        
    Raises:
        TimecodeError: Si la valeur est négative
    """
    if seconds < 0:
        raise TimecodeError(f"Les secondes ne peuvent pas être négatives: {seconds}")
    
    # Séparer la partie entière et décimale
    whole_seconds = int(seconds)
    milliseconds = int((seconds - whole_seconds) * 1000)
    
    # Calcul des heures, minutes, secondes
    hours = whole_seconds // 3600
    remaining_seconds = whole_seconds % 3600
    minutes = remaining_seconds // 60
    secs = remaining_seconds % 60
    
    # Formatage
    if include_milliseconds and milliseconds > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"
    else:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_duration(seconds: Union[int, float]) -> str:
    """
    Formate une durée en secondes en string lisible.
    
    Args:
        seconds: Durée en secondes
        
    Returns:
        str: Durée formatée (ex: "1h 23m 45s", "23m 45s", "45s")
    """
    if seconds < 0:
        return "0s"
    
    whole_seconds = int(seconds)
    hours = whole_seconds // 3600
    remaining_seconds = whole_seconds % 3600
    minutes = remaining_seconds // 60
    secs = remaining_seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:  # Toujours afficher les secondes si c'est la seule unité
        parts.append(f"{secs}s")
    
    return " ".join(parts)


def validate_timecode_range(start_s: float, end_s: float, max_duration_s: float = None) -> bool:
    """
    Valide qu'un range de timecode est cohérent.
    
    Args:
        start_s: Début en secondes
        end_s: Fin en secondes
        max_duration_s: Durée maximum autorisée (optionnel)
        
    Returns:
        bool: True si le range est valide
        
    Raises:
        TimecodeError: Si le range est invalide
    """
    if start_s < 0:
        raise TimecodeError(f"Le timecode de début ne peut pas être négatif: {start_s}")
    
    if end_s < 0:
        raise TimecodeError(f"Le timecode de fin ne peut pas être négatif: {end_s}")
    
    if end_s <= start_s:
        raise TimecodeError(
            f"Le timecode de fin ({end_s}s) doit être supérieur au timecode de début ({start_s}s)"
        )
    
    if max_duration_s is not None and end_s > max_duration_s:
        raise TimecodeError(
            f"Le timecode de fin ({end_s}s) dépasse la durée maximum ({max_duration_s}s)"
        )
    
    return True


def adjust_timecode_to_keyframe(timecode_s: float, keyframes_s: list[float], tolerance_s: float = 2.0) -> float:
    """
    Ajuste un timecode au keyframe le plus proche dans une tolérance donnée.
    
    Args:
        timecode_s: Timecode à ajuster en secondes
        keyframes_s: Liste des positions de keyframes en secondes
        tolerance_s: Tolérance maximum pour l'ajustement
        
    Returns:
        float: Timecode ajusté ou original si aucun keyframe dans la tolérance
    """
    if not keyframes_s:
        return timecode_s
    
    # Trouver le keyframe le plus proche
    closest_keyframe = min(keyframes_s, key=lambda k: abs(k - timecode_s))
    distance = abs(closest_keyframe - timecode_s)
    
    # Si dans la tolérance, utiliser le keyframe
    if distance <= tolerance_s:
        return closest_keyframe
    
    return timecode_s