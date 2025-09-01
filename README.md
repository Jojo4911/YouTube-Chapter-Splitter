# YouTube Chapter Splitter

Un outil de découpage précis de vidéos YouTube par chapitre, développé en Python avec une architecture modulaire et extensible.

## 🎯 Objectifs

- **Téléchargement** de vidéos YouTube en haute qualité (jusqu'à 4K)
- **Extraction** automatique des chapitres depuis métadonnées YouTube
- **Découpage précis** au niveau de la frame avec FFmpeg et ré-encodage
- **Conservation** de tous les chapitres (pas de filtrage dans cette version)
- **Structure organisée** des fichiers de sortie avec nommage sûr cross-platform

## ✨ Fonctionnalités

### 🎉 MVP Fonctionnel (Étapes 1-2 + Crop + GPU + Sous-titres terminées)
- [x] Architecture modulaire avec Pydantic et Typer
- [x] **Téléchargement YouTube** avec yt-dlp et cache intelligent
- [x] **Extraction des métadonnées** et chapitres automatique
- [x] **Découpage FFmpeg** frame-accurate avec ré-encodage
- [x] **Crop vidéo intégré** pour enlever barres des tâches (tutoriels)
- [x] **🚀 Accélération GPU NVIDIA** (NVENC) avec fallback automatique CPU
- [x] **📝 Sous-titres automatiques** : téléchargement depuis YouTube + découpage par chapitre
- [x] **🗂 Support SRT/VTT** : fichiers externes ou téléchargement auto multi-langues
- [x] **⚙️ Synchronisation avancée** : offset temporel, durée minimale, validation
- [x] **Planification des segments** avec validation complète
- [x] **Gestion des noms sûrs** pour Windows/Linux/Mac
- [x] **Validation des durées** avec FFprobe et tolérance
- [x] **Retry automatique** avec presets plus lents si échec
- [x] **Barre de progression** et estimation temps de traitement
- [x] Parsing robuste des timecodes (HH:MM:SS, MM:SS, SS)
- [x] Configuration flexible via YAML
- [x] Interface CLI complète et intuitive
- [x] **72+ tests unitaires** et tests d'intégration complets

### 🔮 Prochaines étapes (V2)
- [ ] Parsing des chapitres depuis description vidéo
- [ ] Export de manifestes détaillés (JSON, CSV, Markdown)
- [ ] Traitement parallèle optimisé
- [ ] Interface graphique (Streamlit)
- [ ] Support multi-plateformes (Vimeo, fichiers locaux)

## 🛠 Installation

### Prérequis
- Python 3.10+
- FFmpeg installé et accessible dans le PATH (avec support NVENC pour GPU)
- yt-dlp (installé automatiquement)
- **Optionnel** : GPU NVIDIA avec drivers CUDA pour accélération

### Installation en mode développement
```bash
git clone <repository-url>
cd YouTube_Chapter_Splitter
pip install -e .
```

### Installation des dépendances uniquement
```bash
pip install -r requirements.txt
```

## 🚀 Utilisation

### Interface ligne de commande

```bash
# Afficher l'aide générale
python -m ytsplit --help

# Découpage d'une vidéo YouTube
python -m ytsplit split "https://www.youtube.com/watch?v=VIDEO_ID"

# Avec options personnalisées
python -m ytsplit split "URL" --out ./mes_videos --quality 720p --crf 20 --preset fast

# Mode simulation pour vérifier le plan (sans téléchargement ni découpage)
python -m ytsplit split "URL" --dry-run --verbose

# Traitement de plusieurs vidéos
python -m ytsplit split "URL1" "URL2" "URL3" --max-parallel 4

# Générer un fichier de configuration par défaut
python -m ytsplit config-init settings.yaml
```

### Exemples d'utilisation réelle

```bash
# Découpage rapide avec preset ultrafast (pour tests)
python -m ytsplit split "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --preset ultrafast --crf 30

# Découpage haute qualité avec preset lent
python -m ytsplit split "URL" --preset slow --crf 16 --audio-bitrate 256k

# 🎬 CROP POUR TUTORIELS - Enlever la barre des tâches Windows
python -m ytsplit split "URL" --crop-bottom 40                    # Barre des tâches standard
python -m ytsplit split "URL" --crop-top 10 --crop-bottom 50      # + Marge haute
python -m ytsplit split "URL" --crop-bottom 40 --preset fast      # Crop + qualité optimisée

# 🚀 ACCÉLÉRATION GPU NVIDIA - Performance optimale
python -m ytsplit split "URL" --gpu                               # GPU avec preset p7 (qualité)
python -m ytsplit split "URL" --gpu --gpu-preset p1               # GPU rapide (57% plus rapide)
python -m ytsplit split "URL" --gpu --gpu-encoder hevc_nvenc      # Encodeur HEVC GPU
python -m ytsplit split "URL" --gpu --crop-bottom 40              # GPU + crop combinés

# 📝 SOUS-TITRES AUTOMATIQUES - Découpage par chapitre
python -m ytsplit split "URL" --subtitles                         # Téléchargement auto + découpage
python -m ytsplit split "URL" --subtitles-file ./mes_srt.srt      # Fichier SRT externe
python -m ytsplit split "URL" --subtitles --subtitles-languages fr,en   # Langues prioritaires
python -m ytsplit split "URL" --subtitles --subtitles-offset 0.5  # Correction décalage temporel
python -m ytsplit split "URL" --subtitles --gpu --crop-bottom 40  # Sous-titres + GPU + crop

# Contrôle du workflow
python -m ytsplit split "URL" --keep-source --no-skip-existing --tolerance 0.5
```

### Configuration

Le projet supporte la configuration via fichier YAML :

```yaml
# settings.yaml
out_dir: "./output"                    # Répertoire des vidéos découpées
work_dir: "./cache"                    # Cache des téléchargements
quality: "1080p"                       # Qualité de téléchargement
video_format: "mp4"                    # Format de sortie

# Encodage vidéo x264
x264:
  crf: 18                             # Facteur qualité (0-51, plus bas = meilleur)
  preset: "veryfast"                  # Vitesse d'encodage

# Audio
audio:
  codec: "aac"                        # Codec audio
  bitrate: "192k"                     # Bitrate audio

# Traitement parallèle
parallel:
  max_workers: 2                      # Nombre de processus FFmpeg simultanés

# Validation des résultats
validation:
  tolerance_seconds: 0.15             # Tolérance durée (secondes)
  max_retries: 1                      # Nombre de retry en cas d'échec

# Nommage des fichiers
naming:
  template: "{n:02d} - {title}"       # Template des noms de chapitres
  sanitize_maxlen: 120                # Longueur max des noms
  replace_chars:                      # Caractères remplacés (Windows-safe)
    ":": "："
    "<": "＜"
    ">": "＞"

# 🎬 Crop vidéo (pour tutoriels)
crop:
  enabled: false                      # Activer le recadrage
  top: 0                             # Pixels à rogner en haut
  bottom: 40                         # Pixels à rogner en bas (barre des tâches)
  left: 0                            # Pixels à rogner à gauche
  right: 0                           # Pixels à rogner à droite
  min_width: 640                     # Largeur minimum après crop
  min_height: 480                    # Hauteur minimum après crop

# 🚀 Accélération GPU NVIDIA (NVENC)
gpu:
  enabled: false                      # Activer l'accélération GPU
  encoder: "h264_nvenc"               # Encodeur (h264_nvenc, hevc_nvenc)
  preset: "p7"                        # Preset GPU (p1=rapide, p7=qualité)
  cq: 18                             # Constant Quality (0-51)
  fallback_to_cpu: true              # Retour automatique CPU si GPU indisponible

# 📝 Sous-titres automatiques
subtitles:
  enabled: false                      # Activer le traitement des sous-titres
  auto_download: true                 # Téléchargement auto depuis YouTube
  external_srt_path: null             # Chemin vers fichier SRT externe (optionnel)
  languages: ["fr", "en"]             # Langues prioritaires
  format_priority: ["srt", "vtt"]     # Formats prioritaires
  encoding: "utf-8"                   # Encodage des fichiers
  offset_s: 0.0                       # Offset temporel en secondes
  min_duration_ms: 300                # Durée minimale d'un sous-titre (ms)
  preserve_timing: true               # Préserver timing original
  force_redownload: false             # Forcer retéléchargement

# Options de comportement
keep_source: true                     # Garder les fichiers sources
skip_existing: true                   # Ignorer les fichiers déjà traités
```

## 🏗 Architecture

```
ytsplit/
├── __init__.py           # Package principal avec version
├── __main__.py           # Point d'entrée (python -m ytsplit)
├── cli.py                # Interface CLI Typer complète
├── config.py             # Configuration Pydantic avec YAML
├── models.py             # Modèles de données validés
├── providers/
│   └── youtube.py        # ✅ Téléchargement yt-dlp et extraction métadonnées + sous-titres
├── parsing/
│   └── timecode.py       # ✅ Parsing timecodes HH:MM:SS
├── planning/
│   └── plan.py           # ✅ Planification segments et validation
├── cutting/
│   └── ffmpeg.py         # ✅ Découpage frame-accurate avec retry
├── subtitles/            # ✅ Module sous-titres complet
│   ├── models.py         # ✅ Modèles SubtitleEntry, SubtitleFile
│   ├── parser.py         # ✅ Parsing SRT/VTT avec validation
│   ├── slicer.py         # ✅ Découpage par chapitre + rebasage temporel
│   └── downloader.py     # ✅ Téléchargement YouTube + gestion fichiers externes
├── io/
│   └── naming.py         # ✅ Nommage sûr cross-platform
├── utils/
│   └── ffprobe.py        # ✅ Analyse vidéo et validation durée
└── tests/                # ✅ 72+ tests unitaires complets
    ├── test_timecode.py
    ├── test_models.py
    ├── test_youtube.py
    ├── test_ffmpeg.py
    ├── test_planning.py
    ├── test_subtitle_models.py      # ✅ Tests modèles sous-titres
    ├── test_subtitle_parser.py      # ✅ Tests parsing SRT/VTT
    ├── test_subtitle_slicer.py      # ✅ Tests découpage par chapitre
    └── test_subtitle_downloader.py  # ✅ Tests téléchargement + validation
```

## 🧪 Tests

```bash
# Lancer tous les tests (72+ tests)
python -m pytest ytsplit/tests/ -v

# Tests par module
python -m pytest ytsplit/tests/test_timecode.py -v           # Parsing timecodes (7 tests)
python -m pytest ytsplit/tests/test_models.py -v             # Modèles Pydantic (5 tests)
python -m pytest ytsplit/tests/test_youtube.py -v            # Provider YouTube (7 tests) 
python -m pytest ytsplit/tests/test_ffmpeg.py -v             # Découpage FFmpeg + Crop + GPU (32 tests)
python -m pytest ytsplit/tests/test_planning.py -v           # Planification (16 tests)
python -m pytest ytsplit/tests/test_subtitle_models.py -v    # Modèles sous-titres (12 tests)
python -m pytest ytsplit/tests/test_subtitle_parser.py -v    # Parsing SRT/VTT (18 tests)
python -m pytest ytsplit/tests/test_subtitle_slicer.py -v    # Découpage sous-titres (15 tests)
python -m pytest ytsplit/tests/test_subtitle_downloader.py -v # Téléchargement sous-titres (20 tests)

# Tests d'intégration complets
python -m ytsplit split "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --dry-run --verbose
python -m ytsplit split "URL" --crop-bottom 40 --dry-run --verbose      # Test crop
python -m ytsplit split "URL" --gpu --dry-run --verbose                  # Test GPU
python -m ytsplit split "URL" --subtitles --dry-run --verbose            # Test sous-titres
python -m ytsplit split "URL" --subtitles --gpu --crop-bottom 40 --dry-run --verbose  # Test complet
```

### Couverture actuelle ✅
- **Parsing timecodes** : 100% (7 tests)
- **Modèles Pydantic** : 100% (5 tests)  
- **Provider YouTube** : 100% (7 tests + intégration)
- **Découpage FFmpeg + Crop + GPU** : 100% (32 tests)
- **Planification** : 100% (16 tests)
- **📝 Sous-titres complets** : 100% (65+ tests)
  - **Modèles sous-titres** : SubtitleEntry, SubtitleFile, validation
  - **Parsing SRT/VTT** : Robuste avec nettoyage HTML/WebVTT
  - **Découpage par chapitre** : Rebasage temporel, durée minimale
  - **Téléchargement** : YouTube auto + fichiers externes + validation
- **Tests d'intégration** : Workflow complet + crop + GPU + sous-titres validés

## 📊 Formats et flux de données

### Workflow complet
```
1. 📥 YouTube URL → yt-dlp → Métadonnées + Téléchargement vidéo
2. 📝 Sous-titres (si activés) → Téléchargement auto ou fichier externe
3. 📋 Chapitres extraits → Planification des segments
4. 🚀 Détection GPU → NVENC disponible ? → Accélération ou fallback CPU
5. 🔪 FFmpeg → Découpage vidéo frame-accurate avec ré-encodage (+ crop optionnel)
6. 📄 Sous-titres → Découpage par chapitre + rebasage temporel à 00:00:00
7. ✅ Validation durée → Fichiers organisés par vidéo (.mp4 + .srt)
```

### Structure de sortie
```
output/
└── Rick Astley - Never Gonna Give You Up-dQw4w9WgXcQ/
    ├── 01 - Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster).mp4
    └── 01 - Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster).srt  # Si --subtitles activé
```

### Timecodes supportés
```
01:23:45      # HH:MM:SS
01:23:45.123  # Avec millisecondes
23:45         # MM:SS
23:45.500     # MM:SS avec millisecondes
45            # Secondes uniquement
```

### Exemple de métadonnées extraites
```json
{
  "video_id": "dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up",
  "duration_s": 213.0,
  "chapters": [
    {
      "index": 1,
      "title": "Never Gonna Give You Up",
      "start_s": 0.0,
      "end_s": 213.0
    }
  ]
}
```

## 🎛 Paramètres de qualité

### Encodage vidéo (x264 CPU)
| Preset | Vitesse | Qualité | Usage |
|--------|---------|---------|--------|
| `ultrafast` | ⚡ Très rapide | 👍 Correcte | Tests/développement |
| `veryfast` | ⚡ Rapide | 👍👍 Bonne | **Défaut recommandé** |
| `fast` | ⏱ Normale | 👍👍👍 Très bonne | Production |
| `slow` | 🐌 Lent | 👍👍👍👍 Excellente | Archivage |

### 🚀 Encodage GPU (NVENC)
| Preset | Vitesse | Qualité | Performance vs CPU | Usage |
|--------|---------|---------|-------------------|--------|
| `p1` | ⚡⚡ Ultra rapide | 👍👍 Bonne | **+57% plus rapide** | Tests/production rapide |
| `p4` | ⚡ Rapide | 👍👍👍 Très bonne | +30% plus rapide | Équilibré |
| `p7` | ⏱ Qualité max | 👍👍👍👍 Excellente | -47% plus lent | **Défaut GPU** |

### Facteurs CRF (qualité)
| CRF | Qualité | Taille fichier | Usage |
|-----|---------|----------------|--------|
| `30` | Faible | Très petite | Tests rapides |
| `23` | Correcte | Petite | Streaming |
| `18` | **Élevée** | Normale | **Défaut** |
| `15` | Excellente | Grande | Archivage |

### Fonctionnalités avancées
- ✅ **🚀 Accélération GPU** : NVENC avec fallback automatique CPU
- ✅ **Retry automatique** : Preset plus lent si échec
- ✅ **Validation durée** : FFprobe avec tolérance configurable  
- ✅ **Cache intelligent** : Skip des téléchargements existants
- ✅ **Traitement parallèle** : Plusieurs processus FFmpeg
- ✅ **Nommage sûr** : Windows/Linux/Mac compatible
- ✅ **Crop + GPU** : Pipeline optimisé hwupload→crop→hwdownload

## 🤝 Développement

### Structure des commits
- `feat:` Nouvelles fonctionnalités
- `fix:` Corrections de bugs
- `test:` Ajout/modification de tests
- `docs:` Documentation
- `refactor:` Refactoring sans changement de comportement

### Tests avant commit
```bash
python -m pytest ytsplit/tests/
python -m mypy ytsplit/ --ignore-missing-imports
```

## 📋 État d'avancement

### ✅ Phase 1 - Architecture (Terminée)
- [x] Architecture modulaire avec Pydantic et Typer
- [x] Modèles de données validés avec contraintes
- [x] Parsing robuste des timecodes (7 formats)
- [x] Configuration YAML flexible et complète
- [x] Interface CLI moderne avec Rich
- [x] Tests unitaires (12 tests initiaux)

### ✅ Phase 2 - Découpage Core (Terminée) 
- [x] **Provider YouTube** : yt-dlp + extraction métadonnées
- [x] **Module FFmpeg** : Découpage frame-accurate + retry
- [x] **Planification** : Validation segments + nommage sûr
- [x] **Utilitaires** : FFprobe + analyse durée
- [x] **CLI complète** : Workflow end-to-end opérationnel
- [x] **Tests complets** : 36 tests + intégration validée

### ✅ Phase 2.5 - Crop Tutoriels (Terminée)
- [x] **Configuration crop** : CropSettings avec validation Pydantic
- [x] **Intégration FFmpeg** : Filtre crop automatique avec FFprobe  
- [x] **Options CLI** : --crop-top/bottom/left/right intuitives
- [x] **Tests crop** : 7 tests dédiés (36 tests total)
- [x] **Validation** : Dimensions minimales + gestion d'erreurs

### ✅ Phase 2.6 - Accélération GPU (Terminée)
- [x] **Configuration GPU** : GPUSettings avec validation NVENC
- [x] **Détection automatique** : check_nvenc_availability() robuste
- [x] **Intégration FFmpeg** : h264_nvenc/hevc_nvenc avec fallback CPU
- [x] **Options CLI** : --gpu, --gpu-preset, --gpu-encoder, --gpu-cq
- [x] **Tests GPU** : 12 tests dédiés (48 tests total)
- [x] **Crop + GPU** : Pipeline optimisé hwupload→crop→hwdownload
- [x] **Performance** : +57% plus rapide (preset p1) vs CPU

### 🔮 Phase 3 - Extensions (Futures)
- [ ] **Parsing description** : Extraction chapitres depuis texte
- [ ] **Manifestes** : Export JSON/CSV/Markdown détaillé
- [ ] **Parallélisation** : Optimisation multi-core
- [ ] **Interface web** : Streamlit pour sélection visuelle
- [ ] **Multi-plateformes** : Support Vimeo + fichiers locaux

### 📊 Métriques actuelles
- **Lignes de code** : ~3200+ lignes
- **Couverture tests** : 72+ tests (100% modules core + crop + GPU + sous-titres)
- **Modules** : 8 modules fonctionnels (+ module subtitles complet)
- **Fonctionnalités** : Workflow complet YouTube → Chapitres découpés + crop + GPU + sous-titres

## 🎬 Exemple d'exécution

```bash
$ python -m ytsplit split "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --preset ultrafast --crf 30

>>> Traitement de 1 vidéo(s)

Video 1/1: https://www.youtube.com/watch?v=dQw4w9WgXcQ
  > Extraction des métadonnées...
  > Vidéo: Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster)
  > Durée: 3.5 minutes
  > 1 chapitre(s) détecté(s)
      1. Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster) (213.0s)
  > Vérification du cache...
  > Téléchargement en cours... (cela peut prendre quelques minutes)
  > Téléchargement terminé
  > Fichier téléchargé: dQw4w9WgXcQ.mp4
    Taille: 100.3 MB
  > Planification du découpage...
  > 1 chapitre(s) à traiter
  > Temps estimé: 1.1 minutes
  > Découpage en cours...
Chapitre 1: Rick Astley - Never Gonna Give...                                  

>>> Résultats finaux:
+------------------------------- Statistiques --------------------------------+
| OK  Chapitres réussis: 1                                                    |
| ERR Chapitres échoués: 0                                                    |
| %   Taux de réussite: 100.0%                                                |
| T   Durée totale: 213.0s                                                    |
| P   Temps de traitement: 74.9s                                              |
+-----------------------------------------------------------------------------+
*** Tous les chapitres ont été traités avec succès !
```

**Résultat** : Fichier créé dans `output/Rick Astley - Never Gonna Give You Up-dQw4w9WgXcQ/01 - Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster).mp4`

## 🎬 Exemple avec Crop (Tutoriels)

```bash
$ python -m ytsplit split "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --crop-bottom 40 --preset ultrafast --crf 30 --verbose

>>> Configuration:
| Paramètre             | Valeur    |
|-----------------------|-----------|
| Répertoire de sortie  | output    |
| CRF (qualité)         | 30        |
| Preset                | ultrafast |
| 🎬 Crop activé        | bottom=40 |

>>> Traitement de 1 vidéo(s)

Video 1/1: https://www.youtube.com/watch?v=dQw4w9WgXcQ
  > Extraction des métadonnées...
  > Vidéo: Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster)
  > Résolution source: 1920x1080
  > Résolution après crop: 1920x1040 (40px enlevés en bas)
  > Planification du découpage...
  > Découpage en cours avec crop...
    + Ch.1: 213.0s

>>> Résultats finaux:
*** Tous les chapitres ont été traités avec succès !
```

**Résultat** : Vidéo 1920x1040 sans barre des tâches Windows ! 🎉

## 📝 Exemple avec Sous-titres (Nouvelle fonctionnalité)

```bash
$ python -m ytsplit split "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --subtitles --preset ultrafast --crf 30 --verbose

>>> Configuration:
| Paramètre                 | Valeur    |
|---------------------------|-----------|
| Répertoire de sortie      | output    |
| CRF (qualité)             | 30        |
| Preset                    | ultrafast |
| 📝 Sous-titres activés   | auto FR,EN |

>>> Traitement de 1 vidéo(s)

Video 1/1: https://www.youtube.com/watch?v=dQw4w9WgXcQ
  > Extraction des métadonnées...
  > Vidéo: Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster)
  > Durée: 3.5 minutes
  > 1 chapitre(s) détecté(s)
      1. Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster) (213.0s)
  > Vérification du cache...
  > Téléchargement terminé
  > Traitement des sous-titres...
    ✓ Sous-titres trouvés: fr
    Format: srt, 42 entrées
    ✓ Synchronisation validée
  > Planification du découpage...
  > Découpage en cours...
    + Ch.1: 213.0s
  > Découpage des sous-titres par chapitre...
    ✓ 1 fichier(s) SRT créés

>>> Résultats finaux:
*** Tous les chapitres ont été traités avec succès !
```

**Résultat** : 
- `01 - Rick Astley - Never Gonna Give You Up.mp4` (vidéo)
- `01 - Rick Astley - Never Gonna Give You Up.srt` (sous-titres rebasés à 00:00:00) 🎉

## 🚀 Exemple avec GPU NVIDIA (Performance)

```bash
$ python -m ytsplit split "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --gpu --gpu-preset p1 --verbose

>>> Configuration:
| Paramètre             | Valeur    |
|-----------------------|-----------|
| Répertoire de sortie  | output    |
| CRF (qualité)         | 18        |
| 🚀 GPU NVIDIA         | h264_nvenc preset p1 |

>>> Traitement de 1 vidéo(s)

Video 1/1: https://www.youtube.com/watch?v=dQw4w9WgXcQ
  > Extraction des métadonnées...
  > Vidéo: Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster)
  > 🚀 GPU NVENC détecté et compatible
  > Résolution: 1920x1080, encodage h264_nvenc
  > Découpage GPU en cours...
    + Ch.1: 213.0s

>>> Résultats finaux:
| OK  Chapitres réussis: 1                                                    |
| T   Durée totale: 213.0s                                                    |
| P   Temps de traitement: 25.1s ⚡ (57% plus rapide que CPU)                |
*** Tous les chapitres ont été traités avec succès !
```

### 📊 Comparaison des performances (vidéo 213s):
- **🚀 GPU NVENC p1** : 25.1s **(57% plus rapide)**
- **💻 CPU x264 veryfast** : 39.4s *(référence)*
- **🚀 GPU NVENC p7** : 74.9s *(qualité maximale)*

## 📄 Licence

[À définir]

## 🙏 Remerciements

- **yt-dlp** pour le téléchargement YouTube robuste
- **FFmpeg** pour le découpage vidéo précis
- **Pydantic** pour la validation des données
- **Typer** pour l'interface CLI moderne
# YouTube Chapter Splitter
## Sous-titres (workflow manuel simplifié)

Par défaut, le téléchargement automatique des sous‑titres est désactivé. L’outil privilégie un flux manuel simple et robuste:

- Option A (recommandée): fournir explicitement un fichier externe via `--subtitles-file` (alias `--subs-from`).
- Option B (plug‑and‑play): déposer un fichier SRT/VTT dans `./custom/` (ou dans le dossier de travail `cache/`) en le nommant avec l’ID vidéo.

Recherche automatique locale (sans réseau):

- Pour l’ID `VIDEO_ID`, les chemins suivants sont recherchés dans `cache/` et `./custom/`:
  - `VIDEO_ID.srt`, `VIDEO_ID.vtt`, `VIDEO_ID.en.srt`, `VIDEO_ID.en.vtt`
  - plus largement `VIDEO_ID.*.srt|vtt`
  - et désormais tout fichier qui se termine par `-VIDEO_ID.*.srt|vtt`

Exemples:

```bash
python -m ytsplit.cli split "https://www.youtube.com/watch?v=8JFMiIlSdlg" --subtitles-file ./custom/8JFMiIlSdlg.en.srt
# ou (noms riches côté utilisateur)
# déposer par ex. custom/REPORT COURSE - Session 4-6 (EMEA  America)-8JFMiIlSdlg.en.srt puis
python -m ytsplit.cli split "https://www.youtube.com/watch?v=8JFMiIlSdlg"
```

Notes:

- Le rapprochement se fait par ID vidéo (indépendant du titre et des caractères Windows).
- Vous pouvez réactiver ponctuellement le téléchargement auto (yt‑dlp) via la configuration (`subtitles.auto_download`), mais il est OFF par défaut.
\n### Encodage Windows (accents)
- Sous PowerShell, pour afficher correctement les accents:
  - `chcp 65001 > $null`
  - `[Console]::InputEncoding  = [System.Text.UTF8Encoding]::new($false)`
  - `[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)`
  - `$OutputEncoding = [Console]::OutputEncoding`
- Pour Python dans la session: `$env:PYTHONUTF8='1'` et `$env:PYTHONIOENCODING='utf-8'`.
- PowerShell 7 + Windows Terminal recommandés.

### Dossiers générés et ignorés
- `output/`: sorties vidéo finales (conservé par défaut)
- `cache/`: répertoire de travail (temporaire)
- `custom/`: ressources locales (ex: SRT fournis)
- `test_output/`, `test_work/`, `test_cache/`, `test_crop/`: dossiers de tests – ignorés par Git
- Caches: `__pycache__/`, `.pytest_cache/` – ignorés/supprimables sans risque
