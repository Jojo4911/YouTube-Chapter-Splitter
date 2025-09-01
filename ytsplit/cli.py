"""Interface ligne de commande pour YouTube Chapter Splitter."""

from pathlib import Path
from typing import List, Optional, Annotated
import subprocess
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.table import Table

from .config import Settings
from .models import VideoMeta, ProcessingStats, SplitResult
from .providers.youtube import create_youtube_provider, YouTubeError
from .planning.plan import create_split_planner, PlanningError
from .cutting.ffmpeg import create_ffmpeg_cutter, FFmpegError
from .subtitles import SubtitleDownloader, SubtitleSlicer, create_subtitle_parser

# Configuration Typer
app = typer.Typer(
    name="ytsplit",
    help="YouTube Chapter Splitter - DÃ©coupe prÃ©cis de vidÃ©os YouTube par chapitre",
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
    urls: Annotated[List[str], typer.Argument(help="URL(s) YouTube Ã  traiter")],
    
    # Options de sortie
    out: Annotated[Optional[Path], typer.Option("--out", "-o", help="RÃ©pertoire de sortie")] = None,
    work: Annotated[Optional[Path], typer.Option("--work", "-w", help="RÃ©pertoire de travail temporaire")] = None,
    
    # Options de qualitÃ©
    quality: Annotated[Optional[str], typer.Option("--quality", "-q", help="QualitÃ© vidÃ©o (ex: 1080p, 720p)")] = None,
    crf: Annotated[Optional[int], typer.Option("--crf", help="Facteur de qualitÃ© x264 (0-51, dÃ©faut: 18)")] = None,
    preset: Annotated[Optional[str], typer.Option("--preset", help="Preset d'encodage x264")] = None,
    audio_bitrate: Annotated[Optional[str], typer.Option("--audio-bitrate", help="Bitrate audio (ex: 192k)")] = None,
    
    # Options de nommage
    template: Annotated[Optional[str], typer.Option("--template", help="Template de nommage ({n:02d} - {title})")] = None,
    
    # Options d'export
    export_manifest: Annotated[Optional[str], typer.Option("--export-manifest", help="Formats de manifest (json,csv,md)")] = None,
    
    # Options de traitement
    max_parallel: Annotated[Optional[int], typer.Option("--max-parallel", help="Nombre de processus FFmpeg parallÃ¨les")] = None,
    tolerance: Annotated[Optional[float], typer.Option("--tolerance", help="TolÃ©rance de durÃ©e en secondes")] = None,
    
    # Options de recadrage
    crop_top: Annotated[Optional[int], typer.Option("--crop-top", help="Pixels Ã  rogner en haut")] = None,
    crop_bottom: Annotated[Optional[int], typer.Option("--crop-bottom", help="Pixels Ã  rogner en bas (ex: 40 pour barre des tÃ¢ches)")] = None,
    crop_left: Annotated[Optional[int], typer.Option("--crop-left", help="Pixels Ã  rogner Ã  gauche")] = None,
    crop_right: Annotated[Optional[int], typer.Option("--crop-right", help="Pixels Ã  rogner Ã  droite")] = None,
    
    # Options GPU NVIDIA
    gpu: Annotated[bool, typer.Option("--gpu", help="Activer l'accÃ©lÃ©ration GPU NVIDIA (NVENC)")] = False,
    gpu_encoder: Annotated[Optional[str], typer.Option("--gpu-encoder", help="Encodeur GPU (h264_nvenc, hevc_nvenc)")] = None,
    gpu_preset: Annotated[Optional[str], typer.Option("--gpu-preset", help="Preset GPU (p1=rapide, p7=qualitÃ©, dÃ©faut p7)")] = None,
    gpu_cq: Annotated[Optional[int], typer.Option("--gpu-cq", help="Constant Quality GPU (0-51, dÃ©faut 18)")] = None,
    
    # Options de sous-titres
    subtitles: Annotated[bool, typer.Option("--subtitles", help="Forcer l'activation des sous-titres (activÃ© par dÃ©faut)")] = False,
    no_subtitles: Annotated[bool, typer.Option("--no-subtitles", help="DÃ©sactiver complÃ¨tement le traitement des sous-titres")] = False,
    subtitles_file: Annotated[Optional[Path], typer.Option("--subtitles-file", "--subs-from", help="Fichier SRT/VTT externe Ã  utiliser (--subs-from est l'alias pour compatibilitÃ©)")] = None,
    subtitles_languages: Annotated[Optional[str], typer.Option("--subtitles-languages", help="Langues prioritaires sÃ©parÃ©es par des virgules (ex: fr,en)")] = None,
    subtitles_offset: Annotated[Optional[float], typer.Option("--subtitles-offset", "--subs-offset", help="Offset temporel en secondes (ex: 0.5, -1.2)")] = None,
    subtitles_min_duration: Annotated[Optional[int], typer.Option("--subtitles-min-duration", "--subs-min-duration-ms", help="DurÃ©e minimale des sous-titres en ms (dÃ©faut: 300)")] = None,
    subtitles_encoding: Annotated[Optional[str], typer.Option("--subtitles-encoding", "--subs-encoding", help="Encodage du fichier SRT (dÃ©faut: utf-8)")] = None,
    
    # Options de configuration
    config: Annotated[Optional[Path], typer.Option("--config", "-c", help="Fichier de configuration YAML")] = None,
    
    # Flags
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Mode simulation (ne dÃ©coupe pas)")] = False,
    keep_source: Annotated[bool, typer.Option("--keep-source/--no-keep-source", help="Conserver les fichiers source (supprimÃ©s par dÃ©faut)")] = False,
    skip_existing: Annotated[bool, typer.Option("--skip-existing/--no-skip-existing", help="Ignorer les fichiers existants")] = True,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Mode verbeux")] = False,
    
    # Version
    version: Annotated[bool, typer.Option("--version", callback=version_callback, help="Afficher la version")] = False,
):
    """
    DÃ©coupe une ou plusieurs vidÃ©os YouTube en chapitres individuels.
    
    TÃ©lÃ©charge la vidÃ©o, extrait les chapitres (depuis les mÃ©tadonnÃ©es YouTube ou 
    la description), puis dÃ©coupe chaque chapitre en fichier sÃ©parÃ© avec une 
    prÃ©cision au niveau de la frame. Les sous-titres sont automatiquement dÃ©coupÃ©s
    par chapitre et placÃ©s dans le mÃªme dossier que les vidÃ©os correspondantes.
    
    La vidÃ©o source est automatiquement supprimÃ©e aprÃ¨s le dÃ©coupage pour Ã©conomiser
    l'espace disque. Utilisez --keep-source pour la conserver.
    
    Exemples:
    
        # DÃ©coupage simple (vidÃ©os + sous-titres automatiquement)
        ytsplit "https://www.youtube.com/watch?v=VIDEO_ID"
        
        # Avec fichier SRT externe (intÃ©gration rapide)
        ytsplit "URL" --subs-from "./mes_sous_titres.srt"
        
        # Sans sous-titres du tout
        ytsplit "URL" --no-subtitles
        
        # Plusieurs vidÃ©os avec options personnalisÃ©es
        ytsplit url1 url2 --out ./mes_videos --quality 720p --crf 20
        
        # Options avancÃ©es sous-titres
        ytsplit "URL" --subtitles --subtitles-offset 0.5 --subtitles-languages fr,en
        
        # Utilisation avec SRT global validÃ© (intÃ©gration rapide)
        ytsplit "URL" --subs-from ./global_validated.srt --subs-offset 0.0
        
        # Mode simulation pour vÃ©rifier le plan
        ytsplit "URL" --dry-run --subtitles
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
    
    # Appliquer les options de crop
    crop_options_provided = any([crop_top, crop_bottom, crop_left, crop_right])
    if crop_options_provided:
        settings.crop.enabled = True
        if crop_top is not None:
            settings.crop.top = crop_top
        if crop_bottom is not None:
            settings.crop.bottom = crop_bottom
        if crop_left is not None:
            settings.crop.left = crop_left
        if crop_right is not None:
            settings.crop.right = crop_right
    
    # Appliquer les options GPU
    if gpu:
        settings.gpu.enabled = True
        if gpu_encoder is not None:
            settings.gpu.encoder = gpu_encoder
        if gpu_preset is not None:
            settings.gpu.preset = gpu_preset
        if gpu_cq is not None:
            settings.gpu.cq = gpu_cq
    
    # Appliquer les options de sous-titres
    if no_subtitles:
        # DÃ©sactiver complÃ¨tement les sous-titres si demandÃ©
        settings.subtitles.enabled = False
    else:
        # Activer par dÃ©faut les sous-titres
        settings.subtitles.enabled = True
        
        # Si un fichier SRT externe est fourni, l'utiliser
        if subtitles_file is not None:
            settings.subtitles.external_srt_path = subtitles_file
            settings.subtitles.auto_download = False  # Utilise fichier externe au lieu du tÃ©lÃ©chargement
        else:
            # Utiliser le tÃ©lÃ©chargement automatique des sous-titres YouTube
            settings.subtitles.auto_download = False
        
        # Appliquer les autres options de sous-titres
        if subtitles_languages is not None:
            settings.subtitles.languages = [lang.strip() for lang in subtitles_languages.split(',')]
        if subtitles_offset is not None:
            settings.subtitles.offset_s = subtitles_offset
        if subtitles_min_duration is not None:
            settings.subtitles.min_duration_ms = subtitles_min_duration
        if subtitles_encoding is not None:
            settings.subtitles.encoding = subtitles_encoding
    
    # Affichage de la configuration si mode verbeux
    if settings.verbose:
        show_configuration(settings)
    
    # Validation des URLs
    validated_urls = validate_youtube_urls(urls)
    
    console.print(f"\n[bold blue]>>> Traitement de {len(validated_urls)} vidÃ©o(s)[/bold blue]\n")
    
    # Traitement des vidÃ©os
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
            
            # Mise Ã  jour des statistiques globales
            all_stats.total_chapters += stats.total_chapters
            all_stats.successful_chapters += stats.successful_chapters
            all_stats.failed_chapters += stats.failed_chapters
            all_stats.total_duration_s += stats.total_duration_s
            all_stats.total_processing_time_s += stats.total_processing_time_s
            
        except Exception as e:
            console.print(f"[bold red]>>> Erreur lors du traitement:[/bold red] {str(e)}")
            continue
    
    # Affichage des statistiques finales
    show_final_stats(all_stats)


@app.command()
def config_init(
    path: Annotated[Path, typer.Argument(help="Chemin du fichier de configuration Ã  crÃ©er")] = Path("settings.yaml"),
    force: Annotated[bool, typer.Option("--force", help="Ã‰craser le fichier existant")] = False
):
    """GÃ©nÃ¨re un fichier de configuration par dÃ©faut."""
    
    if path.exists() and not force:
        console.print(f"[yellow]! Le fichier {path} existe dÃ©jÃ . Utilisez --force pour l'Ã©craser.[/yellow]")
        raise typer.Exit(1)
    
    settings = Settings()
    
    try:
        settings.save_to_file(path)
        console.print(f"[green]âœ… Configuration par dÃ©faut crÃ©Ã©e: {path}[/green]")
        
        # Afficher un aperÃ§u de la configuration
        console.print("\n[bold]AperÃ§u de la configuration:[/bold]")
        show_configuration(settings, show_title=False)
        
    except Exception as e:
        console.print(f"[bold red]âŒ Erreur lors de la crÃ©ation du fichier:[/bold red] {str(e)}")
        raise typer.Exit(1)


def load_settings(config_path: Optional[Path], overrides: dict) -> Settings:
    """Charge les paramÃ¨tres depuis fichier et overrides CLI."""
    
    # Charger depuis fichier si spÃ©cifiÃ©
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
            console.print(f"[yellow]! URL ignorÃ©e (pas YouTube): {url}[/yellow]")
    
    if not validated:
        console.print("[bold red]âŒ Aucune URL YouTube valide fournie[/bold red]")
        raise typer.Exit(1)
    
    return validated


def process_single_video(url: str, settings: Settings) -> ProcessingStats:
    """Traite une seule vidÃ©o et retourne les statistiques."""
    import time
    start_time = time.time()
    
    try:
        # CrÃ©er le provider YouTube
        provider = create_youtube_provider(settings)
        
        console.print("  > Extraction des mÃ©tadonnÃ©es...")
        
        # Extraire les mÃ©tadonnÃ©es
        meta = provider.get_video_info(url)
        
        console.print(f"  > VidÃ©o: [bold]{meta.title}[/bold]")
        console.print(f"  > DurÃ©e: {meta.duration_s / 60:.1f} minutes")
        console.print(f"  > {len(meta.chapters)} chapitre(s) dÃ©tectÃ©(s)")
        
        # Afficher les chapitres
        for chapter in meta.chapters:
            duration = chapter.end_s - chapter.start_s
            console.print(f"     {chapter.index:2d}. {chapter.title} ({duration:.1f}s)")
        
        if settings.dry_run:
            console.print("  [yellow]> Mode simulation - pas de tÃ©lÃ©chargement ni de dÃ©coupage[/yellow]")
            processing_time = time.time() - start_time
            
            return ProcessingStats(
                total_chapters=len(meta.chapters),
                successful_chapters=len(meta.chapters),  # ConsidÃ©rÃ© comme rÃ©ussi en simulation
                failed_chapters=0,
                total_duration_s=meta.duration_s,
                total_processing_time_s=processing_time
            )
        
        # TÃ©lÃ©chargement (si pas en mode dry_run)
        console.print("  > VÃ©rification du cache...")
        existing_file = provider.get_video_file_path(meta.video_id)
        
        if existing_file and settings.skip_existing:
            console.print(f"  > Fichier dÃ©jÃ  en cache: {existing_file.name}")
            video_file = existing_file
        else:
            console.print("  > TÃ©lÃ©chargement en cours... (cela peut prendre quelques minutes)")
            video_file = provider.download_video(url)
            console.print("  > TÃ©lÃ©chargement terminÃ©")
            
            console.print(f"  > Fichier tÃ©lÃ©chargÃ©: {video_file.name}")
            console.print(f"    Taille: {video_file.stat().st_size / 1024 / 1024:.1f} MB")
        
        # Traitement des sous-titres
        subtitle_file = None
        if settings.subtitles.enabled:
            console.print("  > Traitement des sous-titres...")
            
            try:
                # CrÃ©er le downloader de sous-titres
                subtitle_downloader = SubtitleDownloader(settings.subtitles, provider)
                
                # RÃ©cupÃ©rer le fichier de sous-titres
                subtitle_file = subtitle_downloader.get_subtitle_file(url, meta.video_id, settings.work_dir)
                
                if subtitle_file:
                    console.print(f"    > Sous-titres trouvÃ©s: {subtitle_file.language or 'langue inconnue'}")
                    console.print(f"    Format: {subtitle_file.format}, {subtitle_file.entry_count} entrÃ©es")
                    
                    # Valider la synchronisation
                    if subtitle_downloader.validate_subtitle_sync(subtitle_file, meta.duration_s):
                        console.print("    > Synchronisation validÃ©e")
                    else:
                        console.print("    [yellow]! Attention: synchronisation douteuse[/yellow]")
                else:
                    console.print("    [yellow]! Aucun sous-titre disponible[/yellow]")
                    # Logs d'aide au diagnostic
                    try:
                        available = subtitle_downloader.list_available_subtitles(url)
                        if available:
                            langs = ", ".join(sorted(available.keys()))
                            console.print(f"    > Sous-titres dÃ©tectÃ©s (yt-dlp): {langs}")
                        # Afficher la derniÃ¨re erreur/commande yt-dlp si dispo (provider)
                        if hasattr(provider, 'last_ytdlp_error') and provider.last_ytdlp_error:
                            console.print("    > DÃ©tail yt-dlp:")
                            console.print(Panel(str(provider.last_ytdlp_error)[:2000], title="yt-dlp stderr", subtitle="tronquÃ©"))
                        if hasattr(provider, 'last_ytdlp_command') and provider.last_ytdlp_command:
                            console.print(f"    > DerniÃ¨re commande yt-dlp: {' '.join(provider.last_ytdlp_command)}")
                        # Diagnostic direct: essayer `yt-dlp --list-subs` et afficher sortie
                        console.print("    > Diagnostic list-subs (brut)")
                        diag_cmds = []
                        cookies_file = Path('cookies.txt')
                        if cookies_file.exists():
                            diag_cmds.append(["yt-dlp", "--list-subs", "--no-warnings", "--cookies", str(cookies_file), url])
                        for b in ["firefox", "chrome", "edge"]:
                            diag_cmds.append(["yt-dlp", "--list-subs", "--no-warnings", "--cookies-from-browser", b, url])
                        diag_cmds.append(["yt-dlp", "--list-subs", "--no-warnings", url])
                        shown = 0
                        for dc in diag_cmds:
                            try:
                                r = subprocess.run(
                                    dc,
                                    capture_output=True,
                                    text=True,
                                    encoding="utf-8",
                                    errors="replace",
                                    timeout=30,
                                )
                                console.print(f"      $ {' '.join(dc)} -> rc={r.returncode}")
                                if r.stdout:
                                    console.print(Panel(r.stdout[:1200] if len(r.stdout) > 1200 else r.stdout, title="yt-dlp stdout", subtitle="tronquÃ©" if len(r.stdout) > 1200 else ""))
                                if r.stderr:
                                    console.print(Panel(r.stderr[:1200] if len(r.stderr) > 1200 else r.stderr, title="yt-dlp stderr", subtitle="tronquÃ©" if len(r.stderr) > 1200 else ""))
                                shown += 1
                                if shown >= 2:  # Ã©viter de trop inonder
                                    break
                            except Exception as _:
                                continue
                    except Exception as _:
                        pass
                    
            except Exception as e:
                console.print(f"    [yellow]! Erreur sous-titres (non critique): {e}[/yellow]")
                subtitle_file = None
        
        # Planification du dÃ©coupage
        console.print("  > Planification du dÃ©coupage...")
        planner = create_split_planner(settings)
        
        try:
            split_plan = planner.build_split_plan(meta)
        except PlanningError as e:
            console.print(f"  [red]> Erreur de planification: {e}[/red]")
            processing_time = time.time() - start_time
            
            return ProcessingStats(
                total_chapters=len(meta.chapters),
                successful_chapters=0,
                failed_chapters=len(meta.chapters),
                total_duration_s=meta.duration_s,
                total_processing_time_s=processing_time
            )
        
        # Filtrage des fichiers existants
        to_process, existing = planner.filter_existing_files(split_plan)
        
        if existing:
            console.print(f"  > {len(existing)} chapitre(s) dÃ©jÃ  traitÃ©(s) et valide(s)")
        
        if not to_process:
            console.print("  > Tous les chapitres sont dÃ©jÃ  traitÃ©s")
            processing_time = time.time() - start_time
            
            return ProcessingStats(
                total_chapters=len(meta.chapters),
                successful_chapters=len(meta.chapters),
                failed_chapters=0,
                total_duration_s=meta.duration_s,
                total_processing_time_s=processing_time
            )
        
        console.print(f"  > {len(to_process)} chapitre(s) Ã  traiter")
        
        # Estimation du temps de traitement
        estimates = planner.estimate_processing_time(to_process)
        estimated_minutes = estimates["estimated_processing_time"] / 60
        console.print(f"  > Temps estimÃ©: {estimated_minutes:.1f} minutes")
        
        # DÃ©coupage avec FFmpeg
        console.print("  > DÃ©coupage en cours...")
        cutter = create_ffmpeg_cutter(settings)
        
        results = []
        successful = 0
        failed = 0
        
        # Progress bar pour le dÃ©coupage
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            console=console,
            expand=True
        ) as progress:
            task = progress.add_task("DÃ©coupage des chapitres", total=len(to_process))
            
            for plan_item in to_process:
                try:
                    progress.update(task, description=f"Chapitre {plan_item.chapter_index}: {plan_item.chapter_title[:30]}...")
                    
                    result = cutter.cut_precise(video_file, plan_item)
                    results.append(result)
                    
                    if result.status == "OK":
                        successful += 1
                        if settings.verbose:
                            duration = result.obtained_duration_s or 0
                            console.print(f"    + Ch.{plan_item.chapter_index}: {duration:.1f}s")
                    else:
                        failed += 1
                        console.print(f"    - Ch.{plan_item.chapter_index}: {result.message}")
                    
                except Exception as e:
                    failed += 1
                    console.print(f"    - Ch.{plan_item.chapter_index}: Erreur inattendue - {e}")
                
                progress.advance(task)
        
        # Ajouter les fichiers existants aux stats
        successful += len(existing)
        
        # DÃ©coupage des sous-titres
        if settings.subtitles.enabled and subtitle_file:
            console.print("  > DÃ©coupage des sous-titres par chapitre...")
            
            try:
                # CrÃ©er le slicer de sous-titres
                subtitle_slicer = SubtitleSlicer(settings.subtitles)
                
                # DÃ©terminer le rÃ©pertoire de sortie (mÃªme que les vidÃ©os)
                video_output_dir = split_plan[0].output_path.parent if split_plan else settings.out_dir
                
                # DÃ©couper les sous-titres par chapitre
                subtitle_results = subtitle_slicer.slice_subtitles(
                    subtitle_file,
                    meta.chapters,
                    video_output_dir,
                    settings.naming.template
                )
                
                # Afficher les rÃ©sultats
                successful_subs = sum(1 for r in subtitle_results if r.status == "OK")
                empty_subs = sum(1 for r in subtitle_results if r.status == "EMPTY")
                failed_subs = sum(1 for r in subtitle_results if r.status == "ERROR")
                
                console.print(f"    > {successful_subs} fichier(s) SRT crÃ©Ã©s")
                if empty_subs > 0:
                    console.print(f"    - {empty_subs} chapitre(s) sans sous-titres")
                if failed_subs > 0:
                    console.print(f"    [yellow]- {failed_subs} chapitre(s) en erreur[/yellow]")
                    
            except Exception as e:
                console.print(f"    [yellow]! Erreur dÃ©coupage sous-titres (non critique): {e}[/yellow]")
        
        # Nettoyage du fichier source si demandÃ©
        if not settings.keep_source:
            try:
                video_file.unlink()
                console.print("  > Fichier source supprimÃ©")
            except Exception as e:
                console.print(f"  [yellow]> Impossible de supprimer le fichier source: {e}[/yellow]")
        
        processing_time = time.time() - start_time
        
        return ProcessingStats(
            total_chapters=len(meta.chapters),
            successful_chapters=successful,
            failed_chapters=failed,
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
    
    except (FFmpegError, PlanningError) as e:
        console.print(f"  [red]> Erreur de traitement: {e}[/red]")
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
        console.print("\n[bold blue]>>> Configuration:[/bold blue]")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("ParamÃ¨tre", style="cyan", no_wrap=True)
    table.add_column("Valeur", style="green")
    
    # ParamÃ¨tres principaux
    table.add_row("RÃ©pertoire de sortie", str(settings.out_dir))
    table.add_row("RÃ©pertoire de travail", str(settings.work_dir))
    table.add_row("QualitÃ©", settings.quality)
    table.add_row("CRF (qualitÃ©)", str(settings.x264.crf))
    table.add_row("Preset", settings.x264.preset)
    table.add_row("Bitrate audio", settings.audio.bitrate)
    table.add_row("Processus parallÃ¨les", str(settings.parallel.max_workers))
    table.add_row("TolÃ©rance durÃ©e", f"{settings.validation.tolerance_seconds}s")
    
    console.print(table)


def show_final_stats(stats: ProcessingStats) -> None:
    """Affiche les statistiques finales."""
    
    console.print(f"\n[bold blue]>>> RÃ©sultats finaux:[/bold blue]")
    
    # Panneau principal avec les stats
    stats_content = f"""
[green]OK  Chapitres rÃ©ussis:[/green] {stats.successful_chapters}
[red]ERR Chapitres Ã©chouÃ©s:[/red] {stats.failed_chapters}
[blue]%   Taux de rÃ©ussite:[/blue] {stats.success_rate:.1f}%
[yellow]T   DurÃ©e totale:[/yellow] {stats.total_duration_s:.1f}s
[cyan]P   Temps de traitement:[/cyan] {stats.total_processing_time_s:.1f}s
    """.strip()
    
    console.print(Panel(stats_content, title="Statistiques", border_style="blue"))
    
    if stats.total_chapters == 0:
        console.print("[yellow]! Aucun chapitre traitÃ©[/yellow]")
    elif stats.success_rate == 100.0:
        console.print("[bold green]*** Tous les chapitres ont Ã©tÃ© traitÃ©s avec succÃ¨s ![/bold green]")
    elif stats.failed_chapters > 0:
        console.print(f"[yellow]! {stats.failed_chapters} chapitre(s) en erreur. VÃ©rifiez les logs.[/yellow]")


if __name__ == "__main__":
    app()

