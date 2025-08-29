"""Intégration YouTube via yt-dlp (vidéo + sous-titres)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs

from ..models import VideoMeta, Chapter
from ..config import Settings


class YouTubeError(Exception):
    """Erreur liée aux opérations YouTube/yt-dlp."""
    pass


class YouTubeProvider:
    """Provider pour interagir avec YouTube via yt-dlp."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.last_ytdlp_error: Optional[str] = None
        self.last_ytdlp_command: Optional[List[str]] = None
        self._validate_ytdlp()

    def _validate_ytdlp(self) -> None:
        try:
            result = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                raise YouTubeError("yt-dlp n'est pas correctement installé")
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            raise YouTubeError(f"yt-dlp n'est pas disponible: {e}")

    # ---------------------------- URL helpers ----------------------------
    def validate_youtube_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            valid_domains = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}
            if parsed.netloc not in valid_domains:
                return False
            if parsed.netloc in {"youtu.be", "www.youtu.be"}:
                return len(parsed.path.lstrip("/")) == 11
            query_params = parse_qs(parsed.query)
            video_id = query_params.get("v", [])
            return len(video_id) == 1 and len(video_id[0]) == 11
        except Exception:
            return False

    def extract_video_id(self, url: str) -> str:
        if not self.validate_youtube_url(url):
            raise YouTubeError(f"URL YouTube invalide: {url}")
        parsed = urlparse(url)
        if parsed.netloc in {"youtu.be", "www.youtu.be"}:
            return parsed.path.lstrip("/")
        query_params = parse_qs(parsed.query)
        return query_params["v"][0]

    # ---------------------------- Metadata ------------------------------
    def get_video_info(self, url: str) -> VideoMeta:
        if not self.validate_youtube_url(url):
            raise YouTubeError(f"URL YouTube invalide: {url}")
        try:
            cmd = ["yt-dlp", "--dump-json", "--no-download", "--no-warnings", url]
            self.last_ytdlp_command = cmd
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                self.last_ytdlp_error = result.stderr
                raise YouTubeError(f"Échec extraction métadonnées: {result.stderr}")
            info = json.loads(result.stdout)
            return self._convert_ytdlp_info_to_meta(info, url)
        except subprocess.TimeoutExpired:
            raise YouTubeError("Timeout lors de l'extraction des métadonnées")
        except Exception as e:
            raise YouTubeError(f"Erreur inattendue lors de l'extraction: {e}")

    def _convert_ytdlp_info_to_meta(self, info: Dict[str, Any], original_url: str) -> VideoMeta:
        video_id = info.get("id", "")
        title = info.get("title", "Titre inconnu")
        duration = info.get("duration", 0)
        if not video_id:
            raise YouTubeError("ID vidéo manquant dans les métadonnées")
        if not duration or duration <= 0:
            raise YouTubeError("Durée vidéo invalide")
        chapters = self._extract_chapters_from_info(info)
        if not chapters:
            chapters = [Chapter(index=1, title=title, start_s=0.0, end_s=float(duration), raw_label=None)]
        return VideoMeta(video_id=video_id, title=title, duration_s=float(duration), chapters=chapters, url=original_url)

    def _extract_chapters_from_info(self, info: Dict[str, Any]) -> List[Chapter]:
        out: List[Chapter] = []
        for i, ch in enumerate(info.get("chapters", []) or [], 1):
            start = float(ch.get("start_time", 0))
            end = float(ch.get("end_time", start))
            title = ch.get("title", f"Chapitre {i}")
            if end > start:
                out.append(Chapter(index=i, title=title, start_s=start, end_s=end, raw_label=None))
        return out

    # ----------------------------- Download video -----------------------
    def download_video(self, url: str, output_dir: Optional[Path] = None) -> Path:
        if not self.validate_youtube_url(url):
            raise YouTubeError(f"URL YouTube invalide: {url}")
        output_dir = output_dir or self.settings.work_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        vid = self.extract_video_id(url)
        template = output_dir / f"{vid}.%(ext)s"
        try:
            # Essayer plusieurs sélections pour max qualité <= settings.quality
            try:
                max_h = int(str(self.settings.quality).rstrip('p'))
            except Exception:
                max_h = 1080
            formats = [
                f"bv*[height<={max_h}][vcodec^=avc1]+ba/best",
                f"bv*[height<={max_h}]+ba/best",
                f"bestvideo[height<={max_h}]+bestaudio/best",
                self.settings.yt_dlp_format,
            ]
            last_err = None
            ok = False
            for fmt in formats:
                cmd = [
                    "yt-dlp",
                    "--format", fmt,
                    "--output", str(template),
                    "--merge-output-format", self.settings.video_format,
                    "--no-warnings",
                    url,
                ]
                self.last_ytdlp_command = cmd
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
                if res.returncode == 0:
                    ok = True
                    self.last_ytdlp_error = None
                    break
                last_err = res.stderr or res.stdout
            if not ok:
                self.last_ytdlp_error = last_err
                raise YouTubeError(f"Échec du téléchargement: {last_err}")
            # Résoudre le fichier téléchargé
            expected = output_dir / f"{vid}.{self.settings.video_format}"
            if expected.exists():
                return expected
            matches = list(output_dir.glob(f"{vid}.*"))
            if matches:
                return matches[0]
            raise YouTubeError(f"Fichier téléchargé introuvable pour {vid}")
        except subprocess.TimeoutExpired:
            self.last_ytdlp_error = "Timeout lors du téléchargement (>30min)"
            raise YouTubeError("Timeout lors du téléchargement (>30min)")
        except Exception as e:
            self.last_ytdlp_error = str(e)
            raise YouTubeError(f"Erreur inattendue lors du téléchargement: {e}")

    def get_video_file_path(self, video_id: str, output_dir: Optional[Path] = None) -> Optional[Path]:
        output_dir = output_dir or self.settings.work_dir
        for ext in ("mp4", "mkv", "webm", "avi"):
            p = output_dir / f"{video_id}.{ext}"
            if p.exists() and p.stat().st_size > 0:
                return p
        return None

    # ------------------------- yt-dlp resilient -------------------------
    def _run_ytdlp_with_auth(self, base_cmd: List[str], url: str, timeout: int = 180) -> subprocess.CompletedProcess:
        result: Optional[subprocess.CompletedProcess] = None
        last_error = None

        # 1) cookies.txt
        cookies_file = Path("cookies.txt")
        if cookies_file.exists():
            cmd = base_cmd + ["--cookies", str(cookies_file), url]
            self.last_ytdlp_command = cmd
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                if result.returncode == 0:
                    self.last_ytdlp_error = None
                    return result
                last_error = f"cookies.txt failed: {result.stderr}"
            except Exception as e:
                last_error = f"cookies.txt error: {e}"

        # 2) cookies-from-browser
        for browser in ("firefox", "chrome", "edge"):
            cmd = base_cmd + ["--cookies-from-browser", browser, url]
            self.last_ytdlp_command = cmd
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                if result.returncode == 0:
                    self.last_ytdlp_error = None
                    return result
                last_error = f"{browser} failed: {result.stderr}"
            except Exception as e:
                last_error = f"{browser} error: {e}"

        # 3) user-agent
        cmd = base_cmd + [
            "--user-agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
            url,
        ]
        self.last_ytdlp_command = cmd
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode == 0:
                self.last_ytdlp_error = None
                return result
        except Exception as e:
            last_error = f"user-agent error: {e}"

        self.last_ytdlp_error = last_error or (result.stderr if result else "Erreur inconnue")
        self.last_ytdlp_command = cmd
        raise YouTubeError(f"Échec de la commande yt-dlp: {self.last_ytdlp_error}")

    def _build_accept_language(self, languages: Optional[List[str]]) -> Optional[str]:
        if not languages:
            return None
        ordered: List[str] = []
        q = 1.0
        for lang in languages[:5]:
            code = (lang or "").strip()
            if not code:
                continue
            if len(code) == 2:
                primary = code.lower()
                region = "FR" if primary == "fr" else "US"
                ordered.append(f"{primary}-{region}")
                ordered.append(f"{primary};q={q:.1f}")
            else:
                ordered.append(code)
            q = max(0.1, q - 0.1)
        return ",".join(ordered)

    def _run_ytdlp_resilient(self, base_cmd: List[str], url: str, timeout: int = 180,
                              languages: Optional[List[str]] = None) -> subprocess.CompletedProcess:
        headers: List[str] = []
        al = self._build_accept_language(languages)
        if al:
            headers = ["--add-header", f"Accept-Language: {al}"]
        try:
            clients = list(self.settings.subtitles.player_clients)  # type: ignore[attr-defined]
        except Exception:
            clients = ["web", "web_safari", "android"]

        last_err = None
        for client in clients:
            cmd = list(base_cmd) + headers + ["--extractor-args", f"youtube:player_client={client}"]
            self.last_ytdlp_command = cmd
            try:
                res = self._run_ytdlp_with_auth(cmd, url, timeout=timeout)
                if res.returncode == 0:
                    self.last_ytdlp_error = None
                    return res
                last_err = res.stderr
            except Exception as e:
                last_err = str(e)
                continue

        # final try without client
        cmd = list(base_cmd) + headers
        self.last_ytdlp_command = cmd
        try:
            res = self._run_ytdlp_with_auth(cmd, url, timeout=timeout)
            if res.returncode == 0:
                self.last_ytdlp_error = None
                return res
            last_err = res.stderr
        except Exception as e:
            last_err = str(e)
        self.last_ytdlp_error = last_err
        self.last_ytdlp_command = cmd
        raise YouTubeError(f"Echec yt-dlp (toutes variantes): {last_err}")

    # --------------------------- Subtitles ------------------------------
    def get_available_subtitles(self, url: str) -> Dict[str, List[str]]:
        if not self.validate_youtube_url(url):
            raise YouTubeError(f"URL YouTube invalide: {url}")
        base_cmd = ["yt-dlp", "--list-subs", "--no-warnings"]
        langs = None
        try:
            langs = self.settings.subtitles.languages  # type: ignore[attr-defined]
        except Exception:
            pass
        res = self._run_ytdlp_resilient(base_cmd, url, timeout=45, languages=langs)
        available: Dict[str, List[str]] = {}
        import re
        in_section = False
        for line in (res.stdout or "").splitlines():
            s = line.strip()
            if not s:
                continue
            if "available subtitles" in s.lower() or "available automatic captions" in s.lower():
                in_section = True
                continue
            if not in_section:
                continue
            if s.startswith("Language") or s.startswith("[") or s.startswith("="):
                continue
            m = re.match(r"^([a-zA-Z-]{2,10})", s)
            if not m:
                continue
            lang_code = m.group(1)
            simple = lang_code.split('-')[0]
            fmts: List[str] = []
            low = s.lower()
            for f in ("srt", "vtt", "ttml"):
                if f in low:
                    fmts.append(f)
            if fmts:
                available[simple] = fmts
                if lang_code != simple:
                    available[lang_code] = fmts
        return available

    def download_subtitles(
        self,
        url: str,
        languages: Optional[List[str]] = None,
        format_priority: Optional[List[str]] = None,
        output_dir: Optional[Path] = None,
    ) -> Optional[Path]:
        if not self.validate_youtube_url(url):
            raise YouTubeError(f"URL YouTube invalide: {url}")
        languages = languages or ["fr", "en"]
        format_priority = format_priority or ["srt", "vtt"]
        output_dir = output_dir or self.settings.work_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            available_subs = self.get_available_subtitles(url)
        except Exception:
            available_subs = {}

        selected_lang = None
        selected_fmt = None
        if available_subs:
            for lang in languages:
                if lang in available_subs:
                    for fmt in format_priority:
                        if fmt in available_subs[lang]:
                            selected_lang, selected_fmt = lang, fmt
                            break
                    if selected_lang:
                        break
        if not selected_lang or not selected_fmt:
            selected_lang = languages[0]
            selected_fmt = format_priority[0]

        vid = self.extract_video_id(url)
        output_template = output_dir / f"{vid}.{selected_lang}.%(ext)s"

        # Préférences
        prefer_manual = True
        fallback_auto = True
        try:
            prefer_manual = self.settings.subtitles.prefer_manual  # type: ignore[attr-defined]
            fallback_auto = self.settings.subtitles.fallback_to_auto  # type: ignore[attr-defined]
        except Exception:
            pass

        def make_cmd(manual: bool, lang: str, fmt: str) -> List[str]:
            cmd = [
                "yt-dlp",
                "--skip-download",
                "--sub-langs", lang,
                "--sub-format", fmt,
                "--output", str(output_template),
                "--no-warnings",
            ]
            cmd.append("--write-subs" if manual else "--write-auto-subs")
            return cmd

        attempts: List[List[str]] = []
        attempts.append(make_cmd(prefer_manual, selected_lang, selected_fmt))

        # variante complète (en-US)
        auto_lang = selected_lang
        if available_subs:
            for detected in available_subs.keys():
                if detected.startswith(selected_lang) and '-' in detected:
                    auto_lang = detected
                    break
        if auto_lang != selected_lang:
            attempts.append(make_cmd(prefer_manual, auto_lang, selected_fmt))

        if fallback_auto:
            attempts.append(make_cmd(not prefer_manual, selected_lang, selected_fmt))
            if auto_lang != selected_lang:
                attempts.append(make_cmd(not prefer_manual, auto_lang, selected_fmt))

        attempts.append(make_cmd(prefer_manual, "en,fr,es,de,it", "srt/vtt/ttml/best"))

        res = None
        last_err = None
        for cmd in attempts:
            try:
                r = self._run_ytdlp_resilient(cmd, url, timeout=180, languages=languages)
                res = r
                if r.returncode == 0:
                    break
                last_err = r.stderr
            except Exception as e:
                last_err = str(e)
                continue
        if res is None or res.returncode != 0:
            raise YouTubeError(f"Sous-titres introuvables: {last_err}")

        # Résoudre le fichier sous-titres
        expected = output_dir / f"{vid}.{selected_lang}.{selected_fmt}"
        if not expected.exists():
            for fmt in ("srt", "vtt", "ttml"):
                alt = output_dir / f"{vid}.{selected_lang}.{fmt}"
                if alt.exists():
                    expected = alt
                    break
        if not expected.exists():
            # n'importe lequel pour cette vidéo
            matches = list(output_dir.glob(f"{vid}.*"))
            subs = [p for p in matches if p.suffix.lower() in (".srt", ".vtt", ".ttml")]
            if subs:
                lang_files = [p for p in subs if selected_lang in p.name]
                expected = lang_files[0] if lang_files else subs[0]
        if expected.exists():
            return expected
        return None

    def get_subtitles_file_path(self, video_id: str, output_dir: Optional[Path] = None) -> Optional[Path]:
        output_dir = output_dir or self.settings.work_dir
        for lang in ("fr", "en", "auto"):
            for ext in ("srt", "vtt"):
                p = output_dir / f"{video_id}.{lang}.{ext}"
                if p.exists() and p.stat().st_size > 0:
                    return p
        for ext in ("srt", "vtt"):
            p = output_dir / f"{video_id}.{ext}"
            if p.exists() and p.stat().st_size > 0:
                return p
        return None

    # ------------------------------ Orchestration -----------------------
    def process_video(self, url: str, force_redownload: bool = False,
                      download_subtitles: bool = False) -> tuple[VideoMeta, Path, Optional[Path]]:
        meta = self.get_video_info(url)
        existing_file = self.get_video_file_path(meta.video_id)
        existing_subs = self.get_subtitles_file_path(meta.video_id) if download_subtitles else None
        if existing_file and not force_redownload:
            if download_subtitles and not existing_subs:
                try:
                    existing_subs = self.download_subtitles(url)
                except YouTubeError:
                    existing_subs = None
            return meta, existing_file, existing_subs
        video_file = self.download_video(url)
        subtitle_file = None
        if download_subtitles:
            try:
                subtitle_file = self.download_subtitles(url)
            except YouTubeError:
                subtitle_file = None
        return meta, video_file, subtitle_file


def create_youtube_provider(settings: Optional[Settings] = None) -> YouTubeProvider:
    if settings is None:
        from ..config import get_default_settings
        settings = get_default_settings()
    return YouTubeProvider(settings)

