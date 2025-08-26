"""Module de génération de noms de fichiers sûrs."""

import re
from pathlib import Path
from typing import Dict, Optional


def generate_safe_filename(
    name: str,
    max_length: int = 120,
    replace_chars: Optional[Dict[str, str]] = None
) -> str:
    """
    Génère un nom de fichier/répertoire sûr pour tous les OS.
    
    Args:
        name: Nom original
        max_length: Longueur maximum
        replace_chars: Dictionnaire de caractères à remplacer
        
    Returns:
        str: Nom sûr et sanitisé
    """
    if replace_chars is None:
        # Caractères par défaut problématiques sur Windows
        replace_chars = {
            "<": "＜", ">": "＞", ":": "：", "\"": "＂", "/": "／", 
            "\\": "＼", "|": "｜", "?": "？", "*": "＊"
        }
    
    # Remplacer les caractères problématiques
    safe_name = name
    for char, replacement in replace_chars.items():
        safe_name = safe_name.replace(char, replacement)
    
    # Nettoyer les espaces multiples et les caractères de contrôle
    safe_name = re.sub(r'\s+', ' ', safe_name)  # Espaces multiples -> un seul
    safe_name = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', safe_name)  # Caractères de contrôle
    
    # Supprimer les espaces en début/fin
    safe_name = safe_name.strip()
    
    # Supprimer les points en fin (problématique sur Windows)
    safe_name = safe_name.rstrip('.')
    
    # Gérer les noms réservés Windows
    windows_reserved = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    
    if safe_name.upper() in windows_reserved:
        safe_name = f"{safe_name}_file"
    
    # Limiter la longueur
    if len(safe_name) > max_length:
        safe_name = safe_name[:max_length].strip()
    
    # S'assurer qu'on a au moins quelque chose
    if not safe_name:
        safe_name = "unnamed"
    
    return safe_name


def handle_filename_collision(
    base_path: Path,
    max_attempts: int = 100
) -> Path:
    """
    Gère les collisions de noms de fichier en ajoutant un suffixe numérique.
    
    Args:
        base_path: Chemin de base souhaité
        max_attempts: Nombre maximum de tentatives
        
    Returns:
        Path: Chemin unique disponible
        
    Raises:
        ValueError: Si aucun nom unique n'est trouvé
    """
    if not base_path.exists():
        return base_path
    
    # Séparer le nom et l'extension
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent
    
    for i in range(2, max_attempts + 2):
        new_name = f"{stem} ({i}){suffix}"
        new_path = parent / new_name
        
        if not new_path.exists():
            return new_path
    
    raise ValueError(f"Impossible de trouver un nom unique après {max_attempts} tentatives")


def create_output_structure(
    video_title: str,
    video_id: str,
    base_output_dir: Path,
    replace_chars: Optional[Dict[str, str]] = None
) -> Path:
    """
    Crée la structure de répertoire de sortie pour une vidéo.
    
    Args:
        video_title: Titre de la vidéo
        video_id: ID unique de la vidéo
        base_output_dir: Répertoire de base
        replace_chars: Caractères à remplacer
        
    Returns:
        Path: Répertoire de sortie créé
    """
    # Créer un nom de répertoire sûr
    safe_title = generate_safe_filename(video_title, max_length=50, replace_chars=replace_chars)
    dir_name = f"{safe_title}-{video_id}"
    
    output_dir = base_output_dir / dir_name
    
    # Gérer les collisions de répertoire
    if output_dir.exists():
        output_dir = handle_filename_collision(output_dir)
    
    # Créer le répertoire
    output_dir.mkdir(parents=True, exist_ok=True)
    
    return output_dir


def validate_filename(name: str) -> tuple[bool, Optional[str]]:
    """
    Valide si un nom de fichier est acceptable.
    
    Args:
        name: Nom à valider
        
    Returns:
        tuple[bool, str]: (is_valid, error_message)
    """
    if not name:
        return False, "Nom vide"
    
    if len(name) > 255:
        return False, f"Nom trop long ({len(name)} > 255 caractères)"
    
    # Caractères interdits
    forbidden_chars = '<>:"/\\|?*'
    for char in forbidden_chars:
        if char in name:
            return False, f"Caractère interdit: '{char}'"
    
    # Caractères de contrôle
    if re.search(r'[\x00-\x1f\x7f-\x9f]', name):
        return False, "Contient des caractères de contrôle"
    
    # Noms réservés Windows
    windows_reserved = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    
    name_upper = Path(name).stem.upper()
    if name_upper in windows_reserved:
        return False, f"Nom réservé Windows: '{name_upper}'"
    
    # Points en fin
    if name.endswith('.'):
        return False, "Ne peut pas finir par un point"
    
    return True, None


def create_chapter_filename_template() -> str:
    """
    Retourne le template par défaut pour les noms de chapitres.
    
    Returns:
        str: Template avec variables {n}, {title}, etc.
    """
    return "{n:02d} - {title}"


def apply_filename_template(
    template: str,
    chapter_index: int,
    chapter_title: str,
    start_s: float = 0,
    end_s: float = 0,
    duration_s: float = 0
) -> str:
    """
    Applique un template de nom de fichier.
    
    Args:
        template: Template avec variables
        chapter_index: Index du chapitre
        chapter_title: Titre du chapitre
        start_s: Début en secondes
        end_s: Fin en secondes
        duration_s: Durée en secondes
        
    Returns:
        str: Nom généré depuis le template
    """
    variables = {
        "n": chapter_index,
        "title": chapter_title,
        "start": int(start_s),
        "end": int(end_s),
        "duration": int(duration_s),
        "start_min": int(start_s // 60),
        "end_min": int(end_s // 60),
        "duration_min": int(duration_s // 60)
    }
    
    try:
        return template.format(**variables)
    except (KeyError, ValueError) as e:
        # Fallback si le template est invalide
        return f"{chapter_index:02d} - {chapter_title}"