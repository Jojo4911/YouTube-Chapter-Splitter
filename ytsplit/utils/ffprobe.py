"""Utilitaires FFprobe pour l'analyse des fichiers vidéo."""

import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional


class FFprobeError(Exception):
    """Exception levée lors d'erreurs FFprobe."""
    pass


def _run_ffprobe_command(cmd: list[str]) -> str:
    """Exécute une commande FFprobe et retourne la sortie."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        
        if result.returncode != 0:
            error_msg = f"FFprobe a échoué (code {result.returncode})"
            if result.stderr:
                error_msg += f": {result.stderr.strip()}"
            raise FFprobeError(error_msg)
        
        return result.stdout.strip()
        
    except subprocess.TimeoutExpired:
        raise FFprobeError("Timeout FFprobe (>30s)")
    except FileNotFoundError:
        raise FFprobeError("FFprobe n'est pas installé ou pas dans le PATH")


def get_video_duration(video_path: Path) -> float:
    """
    Obtient la durée d'un fichier vidéo en secondes.
    
    Args:
        video_path: Chemin du fichier vidéo
        
    Returns:
        float: Durée en secondes
        
    Raises:
        FFprobeError: Si l'analyse échoue
    """
    if not video_path.exists():
        raise FFprobeError(f"Fichier introuvable: {video_path}")
    
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path)
    ]
    
    duration_str = _run_ffprobe_command(cmd)
    
    try:
        return float(duration_str)
    except (ValueError, TypeError):
        raise FFprobeError(f"Durée invalide retournée: '{duration_str}'")


def get_video_info(video_path: Path) -> Dict[str, Any]:
    """
    Obtient les informations complètes d'un fichier vidéo.
    
    Args:
        video_path: Chemin du fichier vidéo
        
    Returns:
        Dict contenant les informations vidéo (format, streams, etc.)
        
    Raises:
        FFprobeError: Si l'analyse échoue
    """
    if not video_path.exists():
        raise FFprobeError(f"Fichier introuvable: {video_path}")
    
    cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(video_path)
    ]
    
    output = _run_ffprobe_command(cmd)
    
    try:
        return json.loads(output)
    except json.JSONDecodeError as e:
        raise FFprobeError(f"Réponse JSON invalide de FFprobe: {e}")


def get_video_resolution(video_path: Path) -> tuple[int, int]:
    """
    Obtient la résolution (largeur, hauteur) d'un fichier vidéo.
    
    Args:
        video_path: Chemin du fichier vidéo
        
    Returns:
        tuple[int, int]: (largeur, hauteur) en pixels
        
    Raises:
        FFprobeError: Si l'analyse échoue
    """
    info = get_video_info(video_path)
    
    # Trouver le premier stream vidéo
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            width = stream.get("width")
            height = stream.get("height") 
            
            if width is not None and height is not None:
                return int(width), int(height)
    
    raise FFprobeError("Aucun stream vidéo trouvé ou dimensions manquantes")


def get_video_framerate(video_path: Path) -> float:
    """
    Obtient le framerate d'un fichier vidéo.
    
    Args:
        video_path: Chemin du fichier vidéo
        
    Returns:
        float: Framerate en FPS
        
    Raises:
        FFprobeError: Si l'analyse échoue
    """
    info = get_video_info(video_path)
    
    # Trouver le premier stream vidéo
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            # Essayer différentes façons d'obtenir le framerate
            fps_str = stream.get("r_frame_rate", "")
            
            if fps_str and "/" in fps_str:
                try:
                    numerator, denominator = fps_str.split("/")
                    fps = float(numerator) / float(denominator)
                    if fps > 0:
                        return fps
                except (ValueError, ZeroDivisionError):
                    pass
            
            # Fallback sur avg_frame_rate
            avg_fps_str = stream.get("avg_frame_rate", "")
            if avg_fps_str and "/" in avg_fps_str:
                try:
                    numerator, denominator = avg_fps_str.split("/")
                    fps = float(numerator) / float(denominator)
                    if fps > 0:
                        return fps
                except (ValueError, ZeroDivisionError):
                    pass
    
    raise FFprobeError("Impossible de déterminer le framerate")


def validate_video_file(video_path: Path) -> Dict[str, Any]:
    """
    Valide un fichier vidéo et retourne ses propriétés principales.
    
    Args:
        video_path: Chemin du fichier vidéo
        
    Returns:
        Dict contenant les propriétés validées:
        - duration: durée en secondes
        - resolution: tuple (largeur, hauteur)
        - framerate: fps
        - file_size: taille en bytes
        - has_video: bool
        - has_audio: bool
        
    Raises:
        FFprobeError: Si la validation échoue
    """
    if not video_path.exists():
        raise FFprobeError(f"Fichier introuvable: {video_path}")
    
    file_size = video_path.stat().st_size
    if file_size == 0:
        raise FFprobeError("Fichier vide")
    
    try:
        info = get_video_info(video_path)
        
        # Analyser les streams
        has_video = False
        has_audio = False
        
        for stream in info.get("streams", []):
            codec_type = stream.get("codec_type", "")
            if codec_type == "video":
                has_video = True
            elif codec_type == "audio":
                has_audio = True
        
        if not has_video:
            raise FFprobeError("Aucun stream vidéo détecté")
        
        # Obtenir les propriétés
        duration = get_video_duration(video_path)
        resolution = get_video_resolution(video_path)
        
        try:
            framerate = get_video_framerate(video_path)
        except FFprobeError:
            framerate = 25.0  # Valeur par défaut
        
        return {
            "duration": duration,
            "resolution": resolution,
            "framerate": framerate,
            "file_size": file_size,
            "has_video": has_video,
            "has_audio": has_audio,
            "path": str(video_path)
        }
        
    except FFprobeError:
        raise
    except Exception as e:
        raise FFprobeError(f"Erreur lors de la validation: {e}")


def get_keyframe_timestamps(video_path: Path, max_keyframes: int = 1000) -> list[float]:
    """
    Obtient les timestamps des keyframes d'un fichier vidéo.
    
    Args:
        video_path: Chemin du fichier vidéo
        max_keyframes: Nombre maximum de keyframes à récupérer
        
    Returns:
        list[float]: Liste des timestamps en secondes
        
    Raises:
        FFprobeError: Si l'analyse échoue
    """
    if not video_path.exists():
        raise FFprobeError(f"Fichier introuvable: {video_path}")
    
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "frame=pkt_pts_time",
        "-of", "csv=p=0",
        "-show_frames",
        "-skip_frame", "nokey",  # Seulement les keyframes
        str(video_path)
    ]
    
    output = _run_ffprobe_command(cmd)
    
    keyframes = []
    for line in output.split('\n'):
        if line.strip():
            try:
                timestamp = float(line.strip())
                keyframes.append(timestamp)
                
                if len(keyframes) >= max_keyframes:
                    break
                    
            except ValueError:
                continue  # Ignorer les lignes invalides
    
    return sorted(keyframes)


def check_ffprobe_availability() -> bool:
    """
    Vérifie si FFprobe est disponible.
    
    Returns:
        bool: True si FFprobe est disponible, False sinon
    """
    try:
        subprocess.run(
            ["ffprobe", "-version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
