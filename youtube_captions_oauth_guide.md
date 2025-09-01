# Implémenter l’API officielle YouTube pour **télécharger des sous‑titres** (captions) en tant que **propriétaire**
> Guide débutant → opérationnel (Markdown)

Ce document récapitule **uniquement** la voie “API officielle YouTube Data + OAuth 2.0” (celle que tu as choisie). Il explique **pourquoi** l’authentification OAuth est nécessaire, **comment** la mettre en place, et fournit un **script Python clé‑en‑main** pour lister/télécharger une piste de sous‑titres (SRT) d’une vidéo **dont tu es propriétaire** (même si la vidéo est *non répertoriée*).

---

## TL;DR
- **Pas de clé API seule** : pour télécharger des captions privés/non répertoriés, il faut **OAuth 2.0** (connexion au **compte Google** qui possède la chaîne/vidéo).
- **Scope à utiliser** : `https://www.googleapis.com/auth/youtube.force-ssl`.
- **Deux appels** : `captions.list` (trouver l’ID de la piste) → `captions.download` (SRT/VTT).
- **Script fourni** : `download_captions.py` (demande l’accès la 1ère fois, puis réutilise `token.json`).

---

## Pourquoi OAuth (et pas une simple clé API)
- Une **clé API** suffit pour des données **publiques**.  
- Pour des ressources **liées à ton compte** (p. ex. captions téléversés sur **ta** vidéo, vidéo *non répertoriée*, etc.), YouTube exige **OAuth 2.0** afin de vérifier que tu es bien **propriétaire**/gestionnaire de la vidéo.  
- **Comptes de service** (Service Accounts) : **non** adaptés à YouTube Data API (pas de chaîne liée), privilégie OAuth “application installée” (Desktop).

---

## Ce que tu as (déjà) fait côté Google Cloud Console
Tu as indiqué avoir :
1. Créé un **projet**.
2. **Activé** *YouTube Data API v3*.
3. Configuré l’**écran de consentement OAuth** (type *External* convient pour un usage perso).
4. Créé des **identifiants OAuth** (*OAuth client ID*), type **Desktop app** et téléchargé le fichier JSON.

> Si le fichier s’appelle `client_secret_<...>.json`, renomme‑le en `client_secret.json` et place‑le à côté du script Python.

---

## Préparer l’environnement local

### 1) Créer un dossier de travail
```bash
mkdir yt_captions && cd yt_captions
```

### 2) Installer les dépendances Python
```bash
python -m pip install --upgrade pip
pip install google-api-python-client google-auth google-auth-oauthlib
```

> Python 3.9+ recommandé. Assure‑toi d’avoir la possibilité d’ouvrir un navigateur sur cette machine (le flux OAuth en a besoin **une seule fois**).

---

## Script Python clé‑en‑main : `download_captions.py`

- Ouvre le navigateur **la première exécution** → tu te connectes au **même compte** que la chaîne → tu acceptes le scope.  
- Un fichier `token.json` est créé (contient le *refresh token*). **Les exécutions suivantes** se font sans re‑login.  
- Le script :
  - liste les pistes via `captions.list` ;
  - privilégie `en-US`, puis `en` ;
  - télécharge le **SRT** via `captions.download`.

> Copie le contenu ci‑dessous dans `download_captions.py` (au même niveau que `client_secret.json`).

```python
# download_captions.py
from __future__ import annotations
import io, os, sys
from typing import Optional

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# Portée qui autorise la gestion/lecture des captions sur les vidéos du compte
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

def get_credentials() -> Credentials:
    token_path = "token.json"
    creds: Optional[Credentials] = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Lance le flux OAuth (ouvre le navigateur)
            flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    return creds

def pick_caption_id(youtube, video_id: str, prefer_langs=("en-US", "en")) -> Optional[str]:
    resp = youtube.captions().list(part="id,snippet", videoId=video_id).execute()
    items = resp.get("items", [])
    if not items:
        return None

    # Priorité: en-US puis en
    for lang in prefer_langs:
        for it in items:
            snip = it.get("snippet", {})
            if snip.get("language") == lang:
                return it["id"]

    # Sinon, renvoyer la première piste disponible
    return items[0]["id"]

def download_caption_srt(youtube, caption_id: str, out_path: str) -> None:
    # tfmt="srt" pour SRT ; mettre "vtt" si besoin
    request = youtube.captions().download(id=caption_id, tfmt="srt")
    with open(out_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            # Optionnel: afficher la progression
            # if status:
            #     print(f"Téléchargement {int(status.progress() * 100)}%")

def main():
    if len(sys.argv) != 2:
        print("Usage: python download_captions.py <VIDEO_ID>")
        print("Exemple: python download_captions.py dQw4w9WgXcQ")
        sys.exit(1)

    video_id = sys.argv[1].strip()
    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    cap_id = pick_caption_id(youtube, video_id)
    if not cap_id:
        print("Aucune piste de sous-titres trouvée sur cette vidéo.")
        sys.exit(2)

    out_file = f"{video_id}.en.srt"
    download_caption_srt(youtube, cap_id, out_file)
    print(f"OK -> {out_file}")

if __name__ == "__main__":
    main()
```

---

## Utilisation

1) Place `client_secret.json` et `download_captions.py` dans le même dossier.  
2) **Première exécution** (ouvre le navigateur pour le consentement) :
```bash
python download_captions.py <VIDEO_ID>
```
3) Le script crée `<VIDEO_ID>.en.srt` dans le dossier courant.

> **Astuce** : pour utiliser un **format VTT**, change `tfmt="srt"` en `tfmt="vtt"` dans `download_caption_srt`.

---

## Dépannage (erreurs fréquentes)

- **403 `insufficientPermissions` / `Forbidden`**
  - Vérifie que tu utilises **OAuth** (pas d’API key seule).
  - Confirme le **scope** `youtube.force-ssl` dans le code.
  - Connecte‑toi au **bon compte Google** (propriétaire de la chaîne/vidéo).

- **404 `captionNotFound`**
  - Il n’y a pas de piste correspondant à `en-US`. Laisse le script retomber sur `en` ou vérifie la liste renvoyée par `captions.list`.

- **Compte de service**
  - Non supporté pour YouTube Data API. Utilise bien **InstalledAppFlow** (Desktop app).

- **Plusieurs chaînes / Brand Account**
  - Au moment du consentement, Google te fait choisir le compte/chaîne. Sélectionne celle qui **possède** la vidéo.

- **Vidéo non répertoriée**
  - OK. L’accès dépend de **qui est connecté via OAuth**, pas de la visibilité publique.

---

## Quotas & coûts (repères)
- Quota par défaut : **10 000 unités/jour** par projet.
- `captions.list` : coût faible (négligeable dans la plupart des cas).
- `captions.download` : **~200 unités** par appel.
- Si besoin, surveille et augmente les quotas dans la console Google Cloud.

---

## Sécurité & bonnes pratiques
- Conserve `client_secret.json` et `token.json` **en privé** (gitignore, coffre de secrets, etc.).
- Tu peux supprimer `token.json` pour forcer un **nouveau** consentement (utile si tu changes de compte).
- Si tu génères un exécutable/outil pour d’autres utilisateurs, crée un **projet** et un **flow OAuth** séparés.

---

## Extensions possibles (optionnel)
- Paramétrer la **langue** depuis la ligne de commande (`--lang en-US`).
- Sortie **VTT** au lieu de SRT.
- Mode **batch** sur une liste de `VIDEO_ID`.
- Accepter des **URL YouTube** et en extraire l’ID automatiquement.

---

## Résumé
Tu as maintenant :
- un **setup OAuth** propre (YouTube Data API v3) ;
- un **script Python** simple et robuste pour télécharger la **piste SRT** de tes vidéos ;
- une **checklist de dépannage** pour les cas courants (permissions/compte, langues, quotas).
