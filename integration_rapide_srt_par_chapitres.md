# IntÃ©gration rapide â€” DÃ©couper un SRT global validÃ© en SRT par chapitre

> Objectif : **ne pas relancer Whisper**. On part dâ€™un **fichier SRT global dÃ©jÃ  validÃ©** (issu de ton module ASR) et on **gÃ©nÃ¨re automatiquement un SRT par chapitre**, parfaitement alignÃ© avec les clips vidÃ©o produits par lâ€™outil de dÃ©coupe.

---

## Vue dâ€™ensemble

1. **EntrÃ©es** :
   - Une **vidÃ©o principale** (YouTube tÃ©lÃ©chargÃ©e) **avec chapitres**.
   - Un **SRT global validÃ©** correspondant Ã  **cette vidÃ©o** (mÃªmes timecodes).
2. **Sorties** :
   - Une **vidÃ©o par chapitre** (dÃ©jÃ  gÃ©rÃ©e par le splitter).
   - Un **SRT par chapitre** (`.srt`) avec les timecodes **rebasÃ©s Ã  00:00:00,000**.
3. **Principe** :
   - Lire le **plan des chapitres** (start_s, end_s).
   - **DÃ©couper** le SRT global par **chevauchement** des sous-titres avec chaque chapitre.
   - **Tronquer** si nÃ©cessaire et **recaler** les timecodes pour dÃ©marrer Ã  `00:00:00,000` dans chaque fichier SRT de chapitre.
   - **RenumÃ©roter** sÃ©quentiellement les entrÃ©es SRT (1, 2, 3â€¦).

---

## HypothÃ¨ses & prÃ©requis

- Le SRT global est **synchronisÃ©** avec **la vidÃ©o tÃ©lÃ©chargÃ©e par le splitter** (mÃªme source, mÃªme montage, aucun offset).
- Les chapitres sont **fiables** : chaque chapitre a des bornes `[t0, t1)` (en secondes) cohÃ©rentes et validÃ©es.
- Python â‰¥ 3.10. DÃ©pendances Python : `srt` (parsing/compose).
- Organisation des sorties : conserver le **mÃªme schÃ©ma de nommage** que les vidÃ©os chapitrÃ©es (sidecar `.srt`).

> âš ï¸ Si un lÃ©ger **offset** est observÃ© entre la vidÃ©o et le SRT (ex. +0,500 s), prÃ©voir une **option dâ€™offset** (ex. `--subs-offset 0.5`) appliquÃ©e **avant** la dÃ©coupe.

---

## IntÃ©gration dans le splitter (sans ajout de transcription)

### 1) Nouveaux paramÃ¨tres CLI (Typer)

- `--subs-from PATH`: chemin vers le **SRT global validÃ©** (obligatoire pour activer la dÃ©coupe de sous-titres).
- `--subs-offset FLOAT`: **optionnel**, en secondes, positif ou nÃ©gatif (dÃ©faut `0.0`).
- `--subs-min-duration-ms INT`: **optionnel**, durÃ©e minimale dâ€™un sous-titre aprÃ¨s dÃ©coupe (dÃ©faut `300` ms).
- `--subs-encoding STR`: **optionnel**, encodage du SRT `utf-8` par dÃ©faut.

**Exemple**Â :

```bash
ytsplit   --url "https://www.youtube.com/watch?v=XXXX"   --work-dir "./out"   --use-chapters true   --subs-from "./subs/global_validated.srt"   --subs-offset 0.0
```

> Si `--subs-from` nâ€™est pas fourni, **aucune** gÃ©nÃ©ration de SRT par chapitre nâ€™est faite (comportement no-op, warning non bloquant).

### 2) Points dâ€™accroche dans le pipeline

- **AprÃ¨s** avoir calculÃ©/validÃ© le **planning des chapitres** et **avant/pendant** lâ€™Ã©tape de dÃ©coupe vidÃ©o, appeler un module `subtitles/slicer.py` qui :
  1. Parse le SRT global (en appliquant `subs-offset` si â‰  0).
  2. ItÃ¨re sur les chapitres `(t0, t1)` pour **sÃ©lectionner, tronquer, dÃ©caler, renumÃ©roter** les sous-titres.
  3. Ã‰crit `N` fichiers `.srt` **aux cÃ´tÃ©s** des clips vidÃ©o, en rÃ©utilisant la **fonction de nommage** dÃ©jÃ  utilisÃ©e pour les `.mp4`.

### 3) SchÃ©ma de nommage

- Si la vidÃ©o chapitre sâ€™appelle `001 - Intro.mp4`, produire `001 - Intro.srt` **dans le mÃªme dossier**.
- Toujours prÃ©server un nommage **safe cross-platform** (remplacements/normalisations identiques Ã  la vidÃ©o).

---

## Algorithme de dÃ©coupe SRT

Pour chaque chapitre `[t0, t1)` (en secondes)Â :

1. Convertir en `timedelta`: `T0 = td(t0)`, `T1 = td(t1)`.
2. **SÃ©lectionner** chaque sous-titre `(start, end, text)` du SRT global qui **chevauche** `[T0, T1)` :
   - ConditionÂ : `end > T0` **et** `start < T1`.
3. **Tronquer** aux bornes du chapitreÂ :
   - `start' = max(start, T0)`
   - `end'   = min(end, T1)`
4. **Rebaser** Ã  0 pour le fichier de chapitreÂ :
   - `start'' = start' - T0`
   - `end''   = end'   - T0`
5. **Filtrer** les entrÃ©es trop courtes aprÃ¨s dÃ©coupe (ex. `< subs-min-duration-ms`), ou forcer `end'' â‰¥ start'' + 300ms`.
6. **RenumÃ©roter** Ã  partir de 1 et **composer** le fichier SRT.

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

    # Appliquer l'offset global si demandÃ©
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
                # Option: soit on skip, soit on Ã©tire au seuil minimal
                # Ici, on Ã©tire minimalement pour Ã©viter des timecodes inversÃ©s
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

- **SRT manquant / introuvable** : warning clair, pas de gÃ©nÃ©ration SRT par chapitre.
- **DÃ©calage visible** (latence fixe) : utiliser `--subs-offset` (ex. `0.5` ou `-0.7`).
- **DÃ©rive trÃ¨s localisÃ©e** (drift) : garder simple en v1 (pas de time-warp). Documenter la limite.
- **Chapitre trop court** : si aucun sous-titre valide aprÃ¨s tronquage, crÃ©er un SRT **vide** (ou ignorer, selon prÃ©fÃ©rence), en loggant lâ€™info.
- **Encodage** : lire/Ã©crire en `utf-8` par dÃ©faut. Option `--subs-encoding` pour sâ€™adapter.
- **Normalisation CRLF/LF** : privilÃ©gier LF (`\n`).

---

## Tests (recommandÃ©s)

- **Unit tests** sur `slice_srt` :
  - Sous-titre qui **dÃ©borde** sur le dÃ©but/fin de chapitre (tronquage).
  - **Chevauchements** multiples.
  - **Chapitres courts** et filtrage/Ã©tirement minimal.
  - **Offset** positif et nÃ©gatif.
- **Test dâ€™intÃ©gration** :
  - GÃ©nÃ©rer un **planning** de 2â€“3 chapitres, **produire les SRT** par chapitre et **vÃ©rifier** :
    - renumÃ©rotation, rebase Ã  0, timecodes croissants,
    - existence et nommage alignÃ©s avec les `.mp4`,
    - absence dâ€™entrÃ©es hors intervalle.

---

## Exemple dâ€™utilisation (fin de pipeline)

```bash
ytsplit   --url "https://www.youtube.com/watch?v=XXXX"   --work-dir "./out"   --use-chapters true   --subs-from "./subs/global_validated.srt"
# -> Produit out/001 - Intro.mp4 et out/001 - Intro.srt, etc.
```

---

## Roadmap lÃ©gÃ¨re (optionnelle)

- DÃ©tection automatique du SRT global si prÃ©sent dans le dossier de travail (convention de nommage).
- Ajout dâ€™un **manifeste JSON** final listant, pour chaque chapitre : nom du clip, bornes, chemin du `.srt`.
- Option future (non activÃ©e par dÃ©faut) : fallback vers ASR si SRT global absent (mais **pas** dans cette intÃ©gration rapide).

---

**RÃ©sumÃ©** : on **rÃ©utilise le SRT global validÃ©** et on lâ€™**alimente** dans un **slicer SRT** intÃ©grÃ© au splitter. Câ€™est simple, robuste et performant : **0 re-transcription**, une seule source dâ€™alignement (le SRT validÃ©), des fichiers `.srt` par chapitre prÃªts Ã  Ãªtre consommÃ©s.

---
## Mise à jour – Workflow manuel conseillé (sans téléchargement auto)
- Le splitter privilégie désormais un flux manuel simple pour les sous-titres.
- Deux usages recommandés:
  - `--subs-from PATH` pour fournir explicitement le SRT global validé.
  - Déposer un fichier SRT/VTT nommé avec l’ID vidéo dans `./custom/` (ou dans `cache/`).
- La recherche locale (par ID) est effectuée automatiquement avant toute tentative réseau.

Exemple:
```bash
python -m ytsplit.cli split "https://www.youtube.com/watch?v=XXXX" \
  --out ./out \
  --subs-from "./subs/global_validated.srt" \
  --subs-offset 0.0
```

Si `--subs-from` n’est pas fourni, placez `./custom/XXXX.srt` (ou `.en.srt`) et lancez simplement la commande `split`.

Vous pouvez aussi utiliser un nom de fichier « riche » incluant le titre, tant que la fin du nom respecte le suffixe `-VIDEO_ID.*.srt|vtt`. Exemple:

```
custom/REPORT COURSE - Session 4-6 (EMEA  America)-8JFMiIlSdlg.en.srt
```