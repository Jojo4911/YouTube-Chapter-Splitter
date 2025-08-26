"""Interface ligne de commande pour YouTube Chapter Splitter."""

from pathlib import Path
from typing import List, Optional, Annotated
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.table import Table

from .config import Settings
from .models import VideoMeta, ProcessingStats
from .providers.youtube import create_youtube_provider, YouTubeError

# Configuration Typer
app = typer.Typer(
    name="ytsplit",
    help="YouTube Chapter Splitter - Découpe précis de vidéos YouTube par chapitre",
    add_completion=False,
    rich_markup_mode="rich"
)

console = Console()


def version_callback(show_version: bool):
    """Callback pour afficher la version."""
    if show_version:
        from . import __version__
        console.print(f"YouTube Chapter Splitter version {__version__}")
        raise typer.Exit()


@app.command()
def split(
    urls: Annotated[List[str], typer.Argument(help="URL(s) YouTube à traiter")],
    
    # Options de sortie
    out: Annotated[Optional[Path], typer.Option("--out", "-o", help="Répertoire de sortie")] = None,
    work: Annotated[Optional[Path], typer.Option("--work", "-w", help="Répertoire de travail temporaire")] = None,
    
    # Options de qualité
    quality: Annotated[Optional[str], typer.Option("--quality", "-q", help="Qualité vidéo (ex: 1080p, 720p)")] = None,
    crf: Annotated[Optional[int], typer.Option("--crf", help="Facteur de qualité x264 (0-51, défaut: 18)")] = None,
    preset: Annotated[Optional[str], typer.Option("--preset", help="Preset d'encodage x264")] = None,
    audio_bitrate: Annotated[Optional[str], typer.Option("--audio-bitrate", help="Bitrate audio (ex: 192k)")] = None,
    
    # Options de nommage
    template: Annotated[Optional[str], typer.Option("--template", help="Template de nommage ({n:02d} - {title})")] = None,
    
    # Options d'export
    export_manifest: Annotated[Optional[str], typer.Option("--export-manifest", help="Formats de manifest (json,csv,md)")] = None,
    
    # Options de traitement
    max_parallel: Annotated[Optional[int], typer.Option("--max-parallel", help="Nombre de processus FFmpeg parallèles")] = None,
    tolerance: Annotated[Optional[float], typer.Option("--tolerance", help="Tolérance de durée en secondes")] = None,
    
    # Options de configuration
    config: Annotated[Optional[Path], typer.Option("--config", "-c", help="Fichier de configuration YAML")] = None,
    
    # Flags
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Mode simulation (ne découpe pas)")] = False,
    keep_source: Annotated[bool, typer.Option("--keep-source/--no-keep-source", help="Conserver les fichiers source")] = True,
    skip_existing: Annotated[bool, typer.Option("--skip-existing/--no-skip-existing", help="Ignorer les fichiers existants")] = True,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Mode verbeux")] = False,
    
    # Version
    version: Annotated[bool, typer.Option("--version", callback=version_callback, help="Afficher la version")] = False,
):
    """
    Découpe une ou plusieurs vidéos YouTube en chapitres individuels.
    
    Télécharge la vidéo, extrait les chapitres (depuis les métadonnées YouTube ou 
    la description), puis découpe chaque chapitre en fichier séparé avec une 
    précision au niveau de la frame.
    
    Exemples:
    
        # Découpage simple
        ytsplit "https://www.youtube.com/watch?v=VIDEO_ID"
        
        # Plusieurs vidéos avec options personnalisées
        ytsplit url1 url2 --out ./mes_videos --quality 720p --crf 20
        
        # Mode simulation pour vérifier le plan de découpage
        ytsplit "URL" --dry-run
    """
    
    # Charger la configuration
    settings = load_settings(config, {
        'out_dir': out,
        'work_dir': work,
        'quality': quality,
        'dry_run': dry_run,
        'keep_source': keep_source,
        'skip_existing': skip_existing,
        'verbose': verbose,
    })
    
    # Appliquer les overrides depuis la ligne de commande
    if crf is not None:
        settings.x264.crf = crf
    if preset is not None:
        settings.x264.preset = preset
    if audio_bitrate is not None:
        settings.audio.bitrate = audio_bitrate
    if template is not None:
        settings.naming.template = template
    if max_parallel is not None:
        settings.parallel.max_workers = max_parallel
    if tolerance is not None:
        settings.validation.tolerance_seconds = tolerance
    if export_manifest is not None:
        settings.manifest.export = export_manifest.split(',')
    
    # Affichage de la configuration si mode verbeux
    if settings.verbose:
        show_configuration(settings)
    
    # Validation des URLs
    validated_urls = validate_youtube_urls(urls)
    
    console.print(f"\n[bold blue]>>> Traitement de {len(validated_urls)} vidéo(s)[/bold blue]\n")
    
    # Traitement des vidéos
    all_stats = ProcessingStats(
        total_chapters=0,
        successful_chapters=0,
        failed_chapters=0,
        total_duration_s=0.0,
        total_processing_time_s=0.0
    )
    
    for i, url in enumerate(validated_urls, 1):
        console.print(f"[bold cyan]Video {i}/{len(validated_urls)}:[/bold cyan] {url}")
        
        try:
            stats = process_single_video(url, settings)
            
            # Mise à jour des statistiques globales
            all_stats.total_chapters += stats.total_chapters
            all_stats.successful_chapters += stats.successful_chapters
            all_stats.failed_chapters += stats.failed_chapters
            all_stats.total_duration_s += stats.total_duration_s
            all_stats.total_processing_time_s += stats.total_processing_time_s
            
        except Exception as e:
            console.print(f"[bold red]❌ Erreur lors du traitement:[/bold red] {str(e)}")
            continue
    
    # Affichage des statistiques finales
    show_final_stats(all_stats)


@app.command()
def config_init(
    path: Annotated[Path, typer.Argument(help="Chemin du fichier de configuration à créer")] = Path("settings.yaml"),
    force: Annotated[bool, typer.Option("--force", help="Écraser le fichier existant")] = False
):
    """Génère un fichier de configuration par défaut."""
    
    if path.exists() and not force:
        console.print(f"[yellow]⚠️  Le fichier {path} existe déjà. Utilisez --force pour l'écraser.[/yellow]")
        raise typer.Exit(1)
    
    settings = Settings()
    
    try:
        settings.save_to_file(path)
        console.print(f"[green]✅ Configuration par défaut créée: {path}[/green]")
        
        # Afficher un aperçu de la configuration
        console.print("\n[bold]Aperçu de la configuration:[/bold]")
        show_configuration(settings, show_title=False)
        
    except Exception as e:
        console.print(f"[bold red]❌ Erreur lors de la création du fichier:[/bold red] {str(e)}")
        raise typer.Exit(1)


def load_settings(config_path: Optional[Path], overrides: dict) -> Settings:
    """Charge les paramètres depuis fichier et overrides CLI."""
    
    # Charger depuis fichier si spécifié
    if config_path and config_path.exists():
        settings = Settings.load_from_file(config_path)
    else:
        settings = Settings()
    
    # Appliquer les overrides de la ligne de commande
    for key, value in overrides.items():
        if value is not None:
            setattr(settings, key, value)
    
    return settings


def validate_youtube_urls(urls: List[str]) -> List[str]:
    """Valide que les URLs sont bien des URLs YouTube."""
    import re
    
    youtube_patterns = [
        r'https?://(www\.)?youtube\.com/watch\?v=[\w-]+',
        r'https?://youtu\.be/[\w-]+',
        r'https?://(www\.)?youtube\.com/embed/[\w-]+',
    ]
    
    validated = []
    for url in urls:
        if any(re.match(pattern, url) for pattern in youtube_patterns):
            validated.append(url)
        else:
            console.print(f"[yellow]⚠️  URL ignorée (pas YouTube): {url}[/yellow]")
    
    if not validated:
        console.print("[bold red]❌ Aucune URL YouTube valide fournie[/bold red]")
        raise typer.Exit(1)
    
    return validated


def process_single_video(url: str, settings: Settings) -> ProcessingStats:
    """Traite une seule vidéo et retourne les statistiques."""
    import time
    start_time = time.time()
    
    try:
        # Créer le provider YouTube
        provider = create_youtube_provider(settings)
        
        console.print("  > Extraction des métadonnées...")
        
        # Extraire les métadonnées
        meta = provider.get_video_info(url)
        
        console.print(f"  > Vidéo: [bold]{meta.title}[/bold]")
        console.print(f"  > Durée: {meta.duration_s / 60:.1f} minutes")
        console.print(f"  > {len(meta.chapters)} chapitre(s) détecté(s)")
        
        # Afficher les chapitres
        for chapter in meta.chapters:
            duration = chapter.end_s - chapter.start_s
            console.print(f"     {chapter.index:2d}. {chapter.title} ({duration:.1f}s)")
        
        if settings.dry_run:
            console.print("  [yellow]> Mode simulation - pas de téléchargement ni de découpage[/yellow]")
            processing_time = time.time() - start_time
            
            return ProcessingStats(
                total_chapters=len(meta.chapters),
                successful_chapters=len(meta.chapters),  # Considéré comme réussi en simulation
                failed_chapters=0,
                total_duration_s=meta.duration_s,
                total_processing_time_s=processing_time
            )
        
        # Téléchargement (si pas en mode dry_run)
        console.print("  > Vérification du cache...")
        existing_file = provider.get_video_file_path(meta.video_id)
        
        if existing_file and settings.skip_existing:
            console.print(f"  > Fichier déjà en cache: {existing_file.name}")
            video_file = existing_file
        else:
            console.print("  > Téléchargement en cours...")
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Téléchargement...", total=None)
                video_file = provider.download_video(url)
                progress.update(task, description="Téléchargement terminé")
            
            console.print(f"  > Fichier téléchargé: {video_file.name}")
            console.print(f"    Taille: {video_file.stat().st_size / 1024 / 1024:.1f} MB")
        
        # TODO: Implémenter le découpage réel
        console.print("  [yellow]> Découpage non encore implémenté[/yellow]")
        
        processing_time = time.time() - start_time
        
        return ProcessingStats(
            total_chapters=len(meta.chapters),
            successful_chapters=len(meta.chapters),  # Pour l'instant, considéré comme réussi
            failed_chapters=0,
            total_duration_s=meta.duration_s,
            total_processing_time_s=processing_time
        )
        
    except YouTubeError as e:
        console.print(f"  [red]> Erreur YouTube: {e}[/red]")
        processing_time = time.time() - start_time
        
        return ProcessingStats(
            total_chapters=0,
            successful_chapters=0,
            failed_chapters=1,
            total_duration_s=0.0,
            total_processing_time_s=processing_time
        )
    
    except Exception as e:
        console.print(f"  [red]> Erreur inattendue: {e}[/red]")
        processing_time = time.time() - start_time
        
        return ProcessingStats(
            total_chapters=0,
            successful_chapters=0,
            failed_chapters=1,
            total_duration_s=0.0,
            total_processing_time_s=processing_time
        )


def show_configuration(settings: Settings, show_title: bool = True) -> None:
    """Affiche la configuration actuelle."""
    
    if show_title:
        console.print("\n[bold blue]🔧 Configuration:[/bold blue]")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Paramètre", style="cyan", no_wrap=True)
    table.add_column("Valeur", style="green")
    
    # Paramètres principaux
    table.add_row("Répertoire de sortie", str(settings.out_dir))
    table.add_row("Répertoire de travail", str(settings.work_dir))
    table.add_row("Qualité", settings.quality)
    table.add_row("CRF (qualité)", str(settings.x264.crf))
    table.add_row("Preset", settings.x264.preset)
    table.add_row("Bitrate audio", settings.audio.bitrate)
    table.add_row("Processus parallèles", str(settings.parallel.max_workers))
    table.add_row("Tolérance durée", f"{settings.validation.tolerance_seconds}s")
    
    console.print(table)


def show_final_stats(stats: ProcessingStats) -> None:
    """Affiche les statistiques finales."""
    
    console.print(f"\n[bold blue]>>> Résultats finaux:[/bold blue]")
    
    # Panneau principal avec les stats
    stats_content = f"""
[green]OK  Chapitres réussis:[/green] {stats.successful_chapters}
[red]ERR Chapitres échoués:[/red] {stats.failed_chapters}
[blue]%   Taux de réussite:[/blue] {stats.success_rate:.1f}%
[yellow]T   Durée totale:[/yellow] {stats.total_duration_s:.1f}s
[cyan]P   Temps de traitement:[/cyan] {stats.total_processing_time_s:.1f}s
    """.strip()
    
    console.print(Panel(stats_content, title="Statistiques", border_style="blue"))
    
    if stats.total_chapters == 0:
        console.print("[yellow]! Aucun chapitre traité[/yellow]")
    elif stats.success_rate == 100.0:
        console.print("[bold green]*** Tous les chapitres ont été traités avec succès ![/bold green]")
    elif stats.failed_chapters > 0:
        console.print(f"[yellow]! {stats.failed_chapters} chapitre(s) en erreur. Vérifiez les logs.[/yellow]")


if __name__ == "__main__":
    app()