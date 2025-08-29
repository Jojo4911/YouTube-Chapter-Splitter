"""Configuration de l'application avec pydantic-settings."""

from pathlib import Path
from typing import Literal, List, Optional
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class X264Settings(BaseModel):
    """Configuration pour l'encodage vidÃ©o x264."""
    crf: int = Field(default=18, ge=0, le=51, description="Facteur de qualitÃ© constante (0=lossless, 51=worst)")
    preset: Literal["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"] = Field(
        default="veryfast", description="Preset de vitesse d'encodage"
    )


class AudioSettings(BaseModel):
    """Configuration pour l'encodage audio."""
    codec: Literal["aac", "mp3", "opus"] = Field(default="aac", description="Codec audio")
    bitrate: str = Field(default="192k", description="Bitrate audio (ex: 192k, 256k)")


class ManifestSettings(BaseModel):
    """Configuration pour l'export des manifestes."""
    export: list[Literal["json", "csv", "md"]] = Field(default=["json", "csv", "md"], description="Formats d'export")
    include_links: bool = Field(default=True, description="Inclure les liens YouTube avec timestamps")


class ValidationSettings(BaseModel):
    """Configuration pour la validation des rÃ©sultats."""
    tolerance_seconds: float = Field(default=0.15, gt=0, description="TolÃ©rance d'erreur de durÃ©e en secondes")
    max_retries: int = Field(default=1, ge=0, description="Nombre maximum de tentatives en cas d'Ã©chec")


class ParallelSettings(BaseModel):
    """Configuration pour le traitement parallÃ¨le."""
    max_workers: int = Field(default=2, ge=1, le=8, description="Nombre maximum de processus FFmpeg simultanÃ©s")


class NamingSettings(BaseModel):
    """Configuration pour le nommage des fichiers."""
    template: str = Field(default="{n:02d} - {title}", description="Template de nommage des fichiers")
    sanitize_maxlen: int = Field(default=120, gt=0, description="Longueur maximum des noms de fichier")
    replace_chars: dict[str, str] = Field(
        default_factory=lambda: {
            "<": "ï¼œ", ">": "ï¼ž", ":": "ï¼š", "\"": "ï¼‚", "/": "ï¼", "\\": "ï¼¼", 
            "|": "ï½œ", "?": "ï¼Ÿ", "*": "ï¼Š"
        },
        description="CaractÃ¨res Ã  remplacer pour Windows"
    )


class CropSettings(BaseModel):
    """Configuration pour le recadrage vidÃ©o."""
    enabled: bool = Field(default=False, description="Activer le recadrage vidÃ©o")
    top: int = Field(default=0, ge=0, description="Pixels Ã  rogner en haut")
    bottom: int = Field(default=0, ge=0, description="Pixels Ã  rogner en bas")
    left: int = Field(default=0, ge=0, description="Pixels Ã  rogner Ã  gauche") 
    right: int = Field(default=0, ge=0, description="Pixels Ã  rogner Ã  droite")
    min_width: int = Field(default=640, gt=0, description="Largeur minimum aprÃ¨s crop")
    min_height: int = Field(default=480, gt=0, description="Hauteur minimum aprÃ¨s crop")


class SubtitleSettings(BaseModel):
    """Configuration pour le traitement des sous-titres."""
    enabled: bool = Field(default=False, description="Activer le traitement des sous-titres")
    auto_download: bool = Field(default=False, description="Téléchargement automatique depuis YouTube")
    external_srt_path: Optional[Path] = Field(None, description="Chemin vers un fichier SRT externe")
    
    # Options de langue et format
    languages: List[str] = Field(default=["fr", "en"], description="Langues prioritaires")
    format_priority: List[str] = Field(default=["srt", "vtt"], description="Formats prioritaires")
    encoding: str = Field(default="utf-8", description="Encodage des fichiers")
    
    # Options de traitement
    offset_s: float = Field(default=0.0, description="Offset temporel en secondes")
    min_duration_ms: int = Field(default=300, ge=100, le=5000, description="DurÃ©e minimale d'un sous-titre")
    
    # Options avancÃ©es
    preserve_timing: bool = Field(default=True, description="PrÃ©server le timing original dans les clips")
    force_redownload: bool = Field(default=False, description="Forcer le retÃ©lÃ©chargement")
    
    prefer_manual: bool = Field(
        default=True,
        description="Privil9gier les sous-titres manuels (Ã©diteur/communautaires) avant les automatiques"
    )
    fallback_to_auto: bool = Field(
        default=True,
        description="Basculer sur les sous-titres automatiques si les manuels sont indisponibles"
    )
    player_clients: List[str] = Field(
        default_factory=lambda: ["web", "web_safari", "android"],
        description="Profils client yt-dlp  essayer pour contourner l'anti-bot"
    )

    @validator('external_srt_path')
    def validate_external_path(cls, v):
        """Valide que le fichier SRT externe existe."""
        if v is not None:
            if not v.exists():
                raise ValueError(f"Fichier SRT externe introuvable: {v}")
            if v.suffix.lower() not in ['.srt', '.vtt']:
                raise ValueError(f"Format de fichier non supportÃ©: {v.suffix}")
        return v
    
    @validator('offset_s')
    def validate_offset(cls, v):
        """Valide l'offset temporel."""
        if abs(v) > 3600:  # 1 heure max
            raise ValueError(f"Offset trop important: {v}s (max: Â±3600s)")
        return v
    
    @property
    def min_duration_s(self) -> float:
        """DurÃ©e minimale en secondes."""
        return self.min_duration_ms / 1000.0


class GPUSettings(BaseModel):
    """Configuration pour l'accÃ©lÃ©ration GPU NVIDIA."""
    enabled: bool = Field(default=False, description="Activer l'accÃ©lÃ©ration GPU NVIDIA")
    encoder: Literal["h264_nvenc", "hevc_nvenc"] = Field(
        default="h264_nvenc", 
        description="Encodeur GPU Ã  utiliser"
    )
    preset: Literal["p1", "p2", "p3", "p4", "p5", "p6", "p7"] = Field(
        default="p7", 
        description="Preset GPU (p1=rapide, p7=meilleure qualitÃ©)"
    )
    cq: int = Field(default=18, ge=0, le=51, description="Constant Quality GPU (Ã©quivalent CRF)")
    fallback_to_cpu: bool = Field(
        default=True, 
        description="Retour automatique CPU si GPU indisponible"
    )


class Settings(BaseSettings):
    """Configuration principale de l'application."""
    
    model_config = SettingsConfigDict(
        env_prefix="YTSPLIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Chemins
    out_dir: Path = Field(default=Path("./output"), description="RÃ©pertoire de sortie des vidÃ©os")
    work_dir: Path = Field(default=Path("./cache"), description="RÃ©pertoire de travail temporaire")
    config_file: Path = Field(default=Path("settings.yaml"), description="Fichier de configuration YAML")
    
    # QualitÃ© vidÃ©o
    video_format: Literal["mp4", "mkv", "avi"] = Field(default="mp4", description="Format conteneur vidÃ©o")
    quality: str = Field(default="1080p", description="QualitÃ© vidÃ©o maximum (ex: 1080p, 720p)")
    yt_dlp_format: str = Field(
        default="bv*[height<=1080]+ba/best/best",
        description="Format yt-dlp pour le tÃ©lÃ©chargement"
    )
    
    # Configuration des modules
    x264: X264Settings = Field(default_factory=X264Settings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    manifest: ManifestSettings = Field(default_factory=ManifestSettings)
    validation: ValidationSettings = Field(default_factory=ValidationSettings)
    parallel: ParallelSettings = Field(default_factory=ParallelSettings)
    naming: NamingSettings = Field(default_factory=NamingSettings)
    crop: CropSettings = Field(default_factory=CropSettings)
    subtitles: SubtitleSettings = Field(default_factory=SubtitleSettings)
    gpu: GPUSettings = Field(default_factory=GPUSettings)
    
    # Options avancÃ©es
    keep_source: bool = Field(default=False, description="Conserver le fichier source aprÃ¨s dÃ©coupage")
    skip_existing: bool = Field(default=True, description="Ignorer les fichiers dÃ©jÃ  existants et valides")
    dry_run: bool = Field(default=False, description="Mode simulation (ne dÃ©coupe pas rÃ©ellement)")
    verbose: bool = Field(default=False, description="Mode verbeux")
    
    def model_post_init(self, __context) -> None:
        """Validation et crÃ©ation des rÃ©pertoires nÃ©cessaires."""
        # CrÃ©er les rÃ©pertoires s'ils n'existent pas
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        # Validation de la qualitÃ©
        if self.quality not in ["2160p", "1440p", "1080p", "720p", "480p", "360p"]:
            raise ValueError(f"QualitÃ© non supportÃ©e: {self.quality}")
    
    @classmethod
    def load_from_file(cls, config_path: Path) -> "Settings":
        """Charge la configuration depuis un fichier YAML."""
        import yaml
        
        if not config_path.exists():
            return cls()
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
            return cls(**config_data)
        except Exception as e:
            raise ValueError(f"Erreur lors du chargement de la configuration: {e}")
    
    def save_to_file(self, config_path: Path) -> None:
        """Sauvegarde la configuration dans un fichier YAML."""
        import yaml
        
        config_dict = self.model_dump(mode='python', exclude={'config_file'})
        
        # Convertir les Path en string pour YAML
        def convert_paths(obj):
            if isinstance(obj, dict):
                return {k: convert_paths(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_paths(item) for item in obj]
            elif isinstance(obj, Path):
                return str(obj)
            return obj
        
        config_dict = convert_paths(config_dict)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True, indent=2)


def get_default_settings() -> Settings:
    """Retourne une instance de configuration par dÃ©faut."""
    return Settings()


