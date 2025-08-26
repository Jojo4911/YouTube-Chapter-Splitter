"""Configuration de l'application avec pydantic-settings."""

from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class X264Settings(BaseModel):
    """Configuration pour l'encodage vidéo x264."""
    crf: int = Field(default=18, ge=0, le=51, description="Facteur de qualité constante (0=lossless, 51=worst)")
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
    """Configuration pour la validation des résultats."""
    tolerance_seconds: float = Field(default=0.15, gt=0, description="Tolérance d'erreur de durée en secondes")
    max_retries: int = Field(default=1, ge=0, description="Nombre maximum de tentatives en cas d'échec")


class ParallelSettings(BaseModel):
    """Configuration pour le traitement parallèle."""
    max_workers: int = Field(default=2, ge=1, le=8, description="Nombre maximum de processus FFmpeg simultanés")


class NamingSettings(BaseModel):
    """Configuration pour le nommage des fichiers."""
    template: str = Field(default="{n:02d} - {title}", description="Template de nommage des fichiers")
    sanitize_maxlen: int = Field(default=120, gt=0, description="Longueur maximum des noms de fichier")
    replace_chars: dict[str, str] = Field(
        default_factory=lambda: {
            "<": "＜", ">": "＞", ":": "：", "\"": "＂", "/": "／", "\\": "＼", 
            "|": "｜", "?": "？", "*": "＊"
        },
        description="Caractères à remplacer pour Windows"
    )


class CropSettings(BaseModel):
    """Configuration pour le recadrage vidéo."""
    enabled: bool = Field(default=False, description="Activer le recadrage vidéo")
    top: int = Field(default=0, ge=0, description="Pixels à rogner en haut")
    bottom: int = Field(default=0, ge=0, description="Pixels à rogner en bas")
    left: int = Field(default=0, ge=0, description="Pixels à rogner à gauche") 
    right: int = Field(default=0, ge=0, description="Pixels à rogner à droite")
    min_width: int = Field(default=640, gt=0, description="Largeur minimum après crop")
    min_height: int = Field(default=480, gt=0, description="Hauteur minimum après crop")


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
    out_dir: Path = Field(default=Path("./output"), description="Répertoire de sortie des vidéos")
    work_dir: Path = Field(default=Path("./cache"), description="Répertoire de travail temporaire")
    config_file: Path = Field(default=Path("settings.yaml"), description="Fichier de configuration YAML")
    
    # Qualité vidéo
    video_format: Literal["mp4", "mkv", "avi"] = Field(default="mp4", description="Format conteneur vidéo")
    quality: str = Field(default="1080p", description="Qualité vidéo maximum (ex: 1080p, 720p)")
    yt_dlp_format: str = Field(
        default="bv*[height<=1080][ext=mp4]+ba/best",
        description="Format yt-dlp pour le téléchargement"
    )
    
    # Configuration des modules
    x264: X264Settings = Field(default_factory=X264Settings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    manifest: ManifestSettings = Field(default_factory=ManifestSettings)
    validation: ValidationSettings = Field(default_factory=ValidationSettings)
    parallel: ParallelSettings = Field(default_factory=ParallelSettings)
    naming: NamingSettings = Field(default_factory=NamingSettings)
    crop: CropSettings = Field(default_factory=CropSettings)
    
    # Options avancées
    keep_source: bool = Field(default=True, description="Conserver le fichier source après découpage")
    skip_existing: bool = Field(default=True, description="Ignorer les fichiers déjà existants et valides")
    dry_run: bool = Field(default=False, description="Mode simulation (ne découpe pas réellement)")
    verbose: bool = Field(default=False, description="Mode verbeux")
    
    def model_post_init(self, __context) -> None:
        """Validation et création des répertoires nécessaires."""
        # Créer les répertoires s'ils n'existent pas
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        # Validation de la qualité
        if self.quality not in ["2160p", "1440p", "1080p", "720p", "480p", "360p"]:
            raise ValueError(f"Qualité non supportée: {self.quality}")
    
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
    """Retourne une instance de configuration par défaut."""
    return Settings()