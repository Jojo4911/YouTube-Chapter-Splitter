# YouTube Chapter Splitter

Un outil de découpage précis de vidéos YouTube par chapitre, développé en Python avec une architecture modulaire et extensible.

## 🎯 Objectifs

- **Téléchargement** de vidéos YouTube en haute qualité (jusqu'à 1080p)
- **Extraction** automatique des chapitres (métadonnées YouTube ou parsing de description)
- **Découpage précis** au niveau de la frame avec FFmpeg
- **Conservation** de tous les chapitres (pas de filtrage dans cette version)
- **Export** de manifestes détaillés (JSON, CSV, Markdown)

## ✨ Fonctionnalités

### MVP Actuel
- [x] Architecture modulaire avec Pydantic et Typer
- [x] Parsing robuste des timecodes (HH:MM:SS, MM:SS, SS)
- [x] Modèles de données validés
- [x] Configuration flexible via YAML
- [x] Interface CLI intuitive
- [x] Tests unitaires complets

### En cours de développement
- [ ] Intégration yt-dlp pour téléchargement
- [ ] Module de découpage FFmpeg
- [ ] Parsing des chapitres depuis description
- [ ] Génération de manifestes
- [ ] Validation post-découpage

## 🛠 Installation

### Prérequis
- Python 3.10+
- FFmpeg installé et accessible dans le PATH
- yt-dlp (installé automatiquement)

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
# Afficher l'aide
python -m ytsplit.cli --help

# Découpage d'une vidéo (quand implémenté)
python -m ytsplit.cli split "https://www.youtube.com/watch?v=VIDEO_ID"

# Avec options personnalisées
python -m ytsplit.cli split "URL" --out ./mes_videos --quality 720p --crf 20

# Mode simulation pour vérifier le plan
python -m ytsplit.cli split "URL" --dry-run

# Générer un fichier de configuration
python -m ytsplit.cli config-init settings.yaml
```

### Configuration

Le projet supporte la configuration via fichier YAML :

```yaml
# settings.yaml
out_dir: "./output"
work_dir: "./cache"
quality: "1080p"
x264:
  crf: 18
  preset: "veryfast"
audio:
  codec: "aac"
  bitrate: "192k"
parallel:
  max_workers: 2
validation:
  tolerance_seconds: 0.15
```

## 🏗 Architecture

```
ytsplit/
├── __init__.py          # Package principal
├── cli.py               # Interface Typer
├── config.py            # Configuration Pydantic
├── models.py            # Modèles de données
├── providers/           # Téléchargement (yt-dlp)
├── parsing/             # Parsing timecodes et chapitres
├── planning/            # Planification des segments
├── cutting/             # Découpage FFmpeg
├── io/                  # Export et nommage
├── utils/               # Utilitaires (ffprobe, etc.)
└── tests/               # Tests unitaires
```

## 🧪 Tests

```bash
# Lancer tous les tests
python -m pytest ytsplit/tests/ -v

# Tests spécifiques
python -m pytest ytsplit/tests/test_timecode.py -v
python -m pytest ytsplit/tests/test_models.py -v
```

### Couverture actuelle
- ✅ Parsing timecodes (100%)
- ✅ Modèles Pydantic (100%)
- ✅ Configuration (fonctionnel)
- ⏳ Intégration complète (en cours)

## 📊 Exemples de formats supportés

### Timecodes
```
01:23:45      # HH:MM:SS
01:23:45.123  # Avec millisecondes
23:45         # MM:SS
23:45.500     # MM:SS avec millisecondes
45            # Secondes uniquement
```

### Structure de chapitres attendue
```
00:00:00 Introduction
00:03:15 Partie 1 - Les bases
00:15:30 Partie 2 - Concepts avancés
00:45:00 Conclusion
```

## 🎛 Paramètres de qualité

### Encodage vidéo (x264)
- **CRF 18** : Qualité élevée (défaut)
- **Preset veryfast** : Bon compromis vitesse/qualité
- **Découpage précis** : Réencodage pour précision frame-accurate

### Audio
- **AAC 192k** : Qualité CD
- **Préservation** des pistes multiples si présentes

## 🔮 Roadmap V2

- **Détection de silences** pour optimiser les points de coupe
- **Support des sous-titres** avec découpage synchronisé  
- **Interface graphique** (Streamlit) pour sélection visuelle
- **Upload automatique** vers plateformes
- **Support multi-plateformes** (Vimeo, fichiers locaux)

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

### ✅ Terminé
- Architecture de base
- Modèles de données Pydantic
- Parsing des timecodes
- Configuration YAML
- Interface CLI Typer
- Tests unitaires

### 🔄 En cours
- Intégration yt-dlp
- Module de découpage FFmpeg
- Tests d'intégration

### 📅 À venir
- Parsing des chapitres
- Génération de manifestes
- Validation complète
- Documentation utilisateur

## 📄 Licence

[À définir]

## 🙏 Remerciements

- **yt-dlp** pour le téléchargement YouTube robuste
- **FFmpeg** pour le découpage vidéo précis
- **Pydantic** pour la validation des données
- **Typer** pour l'interface CLI moderne