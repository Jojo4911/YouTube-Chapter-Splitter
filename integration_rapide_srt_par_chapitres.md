# Intégration rapide — Découper un SRT global validé en SRT par chapitre

> Objectif : **ne pas relancer Whisper**. On part d’un **fichier SRT global déjà validé** (issu de ton module ASR) et on **génère automatiquement un SRT par chapitre**, parfaitement aligné avec les clips vidéo produits par l’outil de découpe.

---

## Vue d’ensemble

1. **Entrées** :
   - Une **vidéo principale** (YouTube téléchargée) **avec chapitres**.
   - Un **SRT global validé** correspondant à **cette vidéo** (mêmes timecodes).
2. **Sorties** :
   - Une **vidéo par chapitre** (déjà gérée par le splitter).
   - Un **SRT par chapitre** (`.srt`) avec les timecodes **rebasés à 00:00:00,000**.
3. **Principe** :
   - Lire le **plan des chapitres** (start_s, end_s).
   - **Découper** le SRT global par **chevauchement** des sous-titres avec chaque chapitre.
   - **Tronquer** si nécessaire et **recaler** les timecodes pour démarrer à `00:00:00,000` dans chaque fichier SRT de chapitre.
   - **Renuméroter** séquentiellement les entrées SRT (1, 2, 3…).

---

## Hypothèses & prérequis

- Le SRT global est **synchronisé** avec **la vidéo téléchargée par le splitter** (même source, même montage, aucun offset).
- Les chapitres sont **fiables** : chaque chapitre a des bornes `[t0, t1)` (en secondes) cohérentes et validées.
- Python ≥ 3.10. Dépendances Python : `srt` (parsing/compose).
- Organisation des sorties : conserver le **même schéma de nommage** que les vidéos chapitrées (sidecar `.srt`).

> ⚠️ Si un léger **offset** est observé entre la vidéo et le SRT (ex. +0,500 s), prévoir une **option d’offset** (ex. `--subs-offset 0.5`) appliquée **avant** la découpe.

---

## Intégration dans le splitter (sans ajout de transcription)

### 1) Nouveaux paramètres CLI (Typer)

- `--subs-from PATH`: chemin vers le **SRT global validé** (obligatoire pour activer la découpe de sous-titres).
- `--subs-offset FLOAT`: **optionnel**, en secondes, positif ou négatif (défaut `0.0`).
- `--subs-min-duration-ms INT`: **optionnel**, durée minimale d’un sous-titre après découpe (défaut `300` ms).
- `--subs-encoding STR`: **optionnel**, encodage du SRT `utf-8` par défaut.

**Exemple** :

```bash
ytsplit   --url "https://www.youtube.com/watch?v=XXXX"   --work-dir "./out"   --use-chapters true   --subs-from "./subs/global_validated.srt"   --subs-offset 0.0
```

> Si `--subs-from` n’est pas fourni, **aucune** génération de SRT par chapitre n’est faite (comportement no-op, warning non bloquant).

### 2) Points d’accroche dans le pipeline

- **Après** avoir calculé/validé le **planning des chapitres** et **avant/pendant** l’étape de découpe vidéo, appeler un module `subtitles/slicer.py` qui :
  1. Parse le SRT global (en appliquant `subs-offset` si ≠ 0).
  2. Itère sur les chapitres `(t0, t1)` pour **sélectionner, tronquer, décaler, renuméroter** les sous-titres.
  3. Écrit `N` fichiers `.srt` **aux côtés** des clips vidéo, en réutilisant la **fonction de nommage** déjà utilisée pour les `.mp4`.

### 3) Schéma de nommage

- Si la vidéo chapitre s’appelle `001 - Intro.mp4`, produire `001 - Intro.srt` **dans le même dossier**.
- Toujours préserver un nommage **safe cross-platform** (remplacements/normalisations identiques à la vidéo).

---

## Algorithme de découpe SRT

Pour chaque chapitre `[t0, t1)` (en secondes) :

1. Convertir en `timedelta`: `T0 = td(t0)`, `T1 = td(t1)`.
2. **Sélectionner** chaque sous-titre `(start, end, text)` du SRT global qui **chevauche** `[T0, T1)` :
   - Condition : `end > T0` **et** `start < T1`.
3. **Tronquer** aux bornes du chapitre :
   - `start' = max(start, T0)`
   - `end'   = min(end, T1)`
4. **Rebaser** à 0 pour le fichier de chapitre :
   - `start'' = start' - T0`
   - `end''   = end'   - T0`
5. **Filtrer** les entrées trop courtes après découpe (ex. `< subs-min-duration-ms`), ou forcer `end'' ≥ start'' + 300ms`.
6. **Renuméroter** à partir de 1 et **composer** le fichier SRT.

---

## Pseudocode / Extrait Python (module `subtitles/slicer.py`)

```python
from __future__ import annotations
from pathlib import Path
from datetime import timedelta
import srt

def slice_srt(
    full_srt_path: Path,
    chapters: list[tuple[float, float]],  # [(start_s, end_s), ...]
    out_dir: Path,
    naming_fn,  # fn(index:int) -> Path (nom .srt)
    subs_offset: float = 0.0,
    min_ms: int = 300,
    encoding: str = "utf-8",
) -> list[Path]:
    text = full_srt_path.read_text(encoding=encoding)
    entries = list(srt.parse(text))

    # Appliquer l'offset global si demandé
    if abs(subs_offset) > 1e-6:
        delta = timedelta(seconds=subs_offset)
        for e in entries:
            e.start += delta
            e.end += delta

    out_files: list[Path] = []

    for i, (start_s, end_s) in enumerate(chapters, start=1):
        T0, T1 = timedelta(seconds=start_s), timedelta(seconds=end_s)
        seg = []
        for e in entries:
            if e.end <= T0 or e.start >= T1:
                continue
            start = max(e.start, T0) - T0
            end   = min(e.end,   T1) - T0
            if end < start:
                end = start
            if (end - start).total_seconds() * 1000 < min_ms:
                # Option: soit on skip, soit on étire au seuil minimal
                # Ici, on étire minimalement pour éviter des timecodes inversés
                end = start + timedelta(milliseconds=min_ms)
                if end > (T1 - T0):
                    end = (T1 - T0)
                    if end <= start:
                        # Trop court en toute fin, on skip
                        continue
            seg.append(srt.Subtitle(index=len(seg)+1, start=start, end=end, content=e.content))

        out_path = out_dir / naming_fn(i)
        out_path.write_text(srt.compose(seg), encoding=encoding)
        out_files.append(out_path)

    return out_files
```

---

## Gestion des erreurs & cas limites

- **SRT manquant / introuvable** : warning clair, pas de génération SRT par chapitre.
- **Décalage visible** (latence fixe) : utiliser `--subs-offset` (ex. `0.5` ou `-0.7`).
- **Dérive très localisée** (drift) : garder simple en v1 (pas de time-warp). Documenter la limite.
- **Chapitre trop court** : si aucun sous-titre valide après tronquage, créer un SRT **vide** (ou ignorer, selon préférence), en loggant l’info.
- **Encodage** : lire/écrire en `utf-8` par défaut. Option `--subs-encoding` pour s’adapter.
- **Normalisation CRLF/LF** : privilégier LF (`\n`).

---

## Tests (recommandés)

- **Unit tests** sur `slice_srt` :
  - Sous-titre qui **déborde** sur le début/fin de chapitre (tronquage).
  - **Chevauchements** multiples.
  - **Chapitres courts** et filtrage/étirement minimal.
  - **Offset** positif et négatif.
- **Test d’intégration** :
  - Générer un **planning** de 2–3 chapitres, **produire les SRT** par chapitre et **vérifier** :
    - renumérotation, rebase à 0, timecodes croissants,
    - existence et nommage alignés avec les `.mp4`,
    - absence d’entrées hors intervalle.

---

## Exemple d’utilisation (fin de pipeline)

```bash
ytsplit   --url "https://www.youtube.com/watch?v=XXXX"   --work-dir "./out"   --use-chapters true   --subs-from "./subs/global_validated.srt"
# -> Produit out/001 - Intro.mp4 et out/001 - Intro.srt, etc.
```

---

## Roadmap légère (optionnelle)

- Détection automatique du SRT global si présent dans le dossier de travail (convention de nommage).
- Ajout d’un **manifeste JSON** final listant, pour chaque chapitre : nom du clip, bornes, chemin du `.srt`.
- Option future (non activée par défaut) : fallback vers ASR si SRT global absent (mais **pas** dans cette intégration rapide).

---

**Résumé** : on **réutilise le SRT global validé** et on l’**alimente** dans un **slicer SRT** intégré au splitter. C’est simple, robuste et performant : **0 re-transcription**, une seule source d’alignement (le SRT validé), des fichiers `.srt` par chapitre prêts à être consommés.

---
## Mise � jour � Workflow manuel conseill� (sans t�l�chargement auto)
- Le splitter privil�gie d�sormais un flux manuel simple pour les sous-titres.
- Deux usages recommand�s:
  - `--subs-from PATH` pour fournir explicitement le SRT global valid�.
  - D�poser un fichier SRT/VTT nomm� avec l�ID vid�o dans `./custom/` (ou dans `cache/`).
- La recherche locale (par ID) est effectu�e automatiquement avant toute tentative r�seau.

Exemple:
```bash
python -m ytsplit.cli split "https://www.youtube.com/watch?v=XXXX" \
  --out ./out \
  --subs-from "./subs/global_validated.srt" \
  --subs-offset 0.0
```

Si `--subs-from` n�est pas fourni, placez `./custom/XXXX.srt` (ou `.en.srt`) et lancez simplement la commande `split`.
