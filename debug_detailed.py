#!/usr/bin/env python3
"""Script de diagnostic ultra-détaillé pour les sous-titres."""

import subprocess
import sys
import traceback
from pathlib import Path

def debug_detailed_subtitles(url="https://www.youtube.com/watch?v=8JFMiIlSdlg"):
    """Debug ultra-détaillé des sous-titres."""
    
    print("="*80)
    print(f"DIAGNOSTIC ULTRA-DETAILLE pour: {url}")
    print("="*80)
    
    # Test 1: yt-dlp --list-subs COMPLET
    print("\n1. YT-DLP --LIST-SUBS (SORTIE COMPLETE)")
    print("-" * 50)
    
    try:
        cmd = ["yt-dlp", "--list-subs", "--no-warnings", url]
        print(f"Commande: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        print(f"Return code: {result.returncode}")
        print(f"STDOUT complet ({len(result.stdout)} chars):")
        print(">" * 40)
        for i, line in enumerate(result.stdout.split('\n')):
            print(f"{i:3d}: {repr(line)}")
        print("<" * 40)
        
        if result.stderr:
            print(f"STDERR complet ({len(result.stderr)} chars):")
            print(">" * 40)
            for i, line in enumerate(result.stderr.split('\n')):
                print(f"{i:3d}: {repr(line)}")
            print("<" * 40)
            
    except Exception as e:
        print(f"ERREUR dans test 1: {e}")
        traceback.print_exc()
    
    # Test 2: Téléchargement SUBS MANUELS seulement
    print("\n2. TEST TELECHARGEMENT SOUS-TITRES MANUELS")
    print("-" * 50)
    
    work_dir = Path("./debug_work")
    work_dir.mkdir(exist_ok=True)
    
    try:
        cmd_manual = [
            "yt-dlp",
            "--write-subs",  # SEULEMENT sous-titres manuels
            "--skip-download",
            "--sub-langs", "all",  # Toutes les langues
            "--sub-format", "srt/vtt/best",  # Tous les formats
            "--output", str(work_dir / "test_manual.%(ext)s"),
            "--verbose",  # Mode verbeux
            url
        ]
        
        print(f"Commande: {' '.join(cmd_manual)}")
        
        result_manual = subprocess.run(cmd_manual, capture_output=True, text=True, timeout=120)
        
        print(f"Return code: {result_manual.returncode}")
        
        if result_manual.stdout:
            print(f"STDOUT ({len(result_manual.stdout)} chars - premiers 2000):")
            print(result_manual.stdout[:2000])
        
        if result_manual.stderr:
            print(f"STDERR ({len(result_manual.stderr)} chars - premiers 2000):")  
            print(result_manual.stderr[:2000])
            
        print("\nFichiers créés:")
        for f in work_dir.iterdir():
            if f.name.startswith("test_manual"):
                print(f"  {f.name} ({f.stat().st_size} bytes)")
                if f.suffix in ['.srt', '.vtt']:
                    content = f.read_text(encoding='utf-8', errors='ignore')
                    print(f"    Contenu (200 premiers chars): {repr(content[:200])}")
    
    except Exception as e:
        print(f"ERREUR dans test 2: {e}")
        traceback.print_exc()
    
    # Test 3: Téléchargement AUTO-SUBS seulement  
    print("\n3. TEST TELECHARGEMENT SOUS-TITRES AUTO")
    print("-" * 50)
    
    try:
        cmd_auto = [
            "yt-dlp", 
            "--write-auto-subs",  # SEULEMENT sous-titres auto
            "--skip-download",
            "--sub-langs", "en,fr",
            "--sub-format", "srt/vtt/best",
            "--output", str(work_dir / "test_auto.%(ext)s"),
            "--verbose",
            url
        ]
        
        print(f"Commande: {' '.join(cmd_auto)}")
        
        result_auto = subprocess.run(cmd_auto, capture_output=True, text=True, timeout=120)
        
        print(f"Return code: {result_auto.returncode}")
        
        if result_auto.stdout:
            print(f"STDOUT ({len(result_auto.stdout)} chars - premiers 1500):")
            print(result_auto.stdout[:1500])
            
        if result_auto.stderr:
            print(f"STDERR ({len(result_auto.stderr)} chars - premiers 1500):")
            print(result_auto.stderr[:1500])
            
        print("\nFichiers créés:")
        for f in work_dir.iterdir():
            if f.name.startswith("test_auto"):
                print(f"  {f.name} ({f.stat().st_size} bytes)")
                if f.suffix in ['.srt', '.vtt']:
                    content = f.read_text(encoding='utf-8', errors='ignore')
                    print(f"    Contenu (200 premiers chars): {repr(content[:200])}")
                    
    except Exception as e:
        print(f"ERREUR dans test 3: {e}")
        traceback.print_exc()
    
    # Test 4: Information sur la vidéo
    print("\n4. INFORMATIONS SUR LA VIDÉO")
    print("-" * 50)
    
    try:
        cmd_info = ["yt-dlp", "--dump-json", "--no-warnings", url]
        print(f"Commande: {' '.join(cmd_info)}")
        
        result_info = subprocess.run(cmd_info, capture_output=True, text=True, timeout=60)
        
        if result_info.returncode == 0:
            import json
            data = json.loads(result_info.stdout)
            
            print(f"Titre: {data.get('title', 'N/A')}")
            print(f"Durée: {data.get('duration', 'N/A')} secondes")
            print(f"Uploader: {data.get('uploader', 'N/A')}")
            
            # Informations sur les sous-titres dans les métadonnées
            subtitles = data.get('subtitles', {})
            auto_captions = data.get('automatic_captions', {})
            
            print(f"\nSubtitles manuels dans JSON: {list(subtitles.keys())}")
            for lang, subs in subtitles.items():
                print(f"  {lang}: {len(subs)} formats - {[s.get('ext', 'unknown') for s in subs]}")
                
            print(f"\nAutomatic captions dans JSON: {list(auto_captions.keys())}")
            if auto_captions:
                # Juste les 3 premières langues pour pas surcharger
                for i, (lang, subs) in enumerate(auto_captions.items()):
                    if i < 3:
                        print(f"  {lang}: {len(subs)} formats - {[s.get('ext', 'unknown') for s in subs]}")
                if len(auto_captions) > 3:
                    print(f"  ... et {len(auto_captions) - 3} autres langues")
        else:
            print(f"Erreur récupération JSON: {result_info.stderr}")
            
    except Exception as e:
        print(f"ERREUR dans test 4: {e}")
        traceback.print_exc()
    
    # Résumé des fichiers créés
    print("\n5. RESUME DES FICHIERS CREES")
    print("-" * 50)
    
    print("Contenu du répertoire debug_work:")
    try:
        for f in sorted(work_dir.iterdir()):
            print(f"  {f.name} ({f.stat().st_size} bytes)")
    except Exception as e:
        print(f"Erreur listing: {e}")
    
    print("\n" + "="*80)
    print("FIN DU DIAGNOSTIC")
    print("="*80)

if __name__ == "__main__":
    debug_detailed_subtitles()