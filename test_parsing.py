#!/usr/bin/env python3
"""Test du parsing exact de get_available_subtitles."""

import sys
sys.path.insert(0, '.')

from ytsplit.providers.youtube import create_youtube_provider
from ytsplit.config import Settings

def test_parsing():
    """Test le parsing exact."""
    
    print("="*60)
    print("TEST DU PARSING get_available_subtitles")
    print("="*60)
    
    settings = Settings()
    provider = create_youtube_provider(settings)
    
    url = "https://www.youtube.com/watch?v=8JFMiIlSdlg"
    
    print("1. Test avec notre fonction get_available_subtitles:")
    try:
        result = provider.get_available_subtitles(url)
        print(f"   Résultat: {result}")
        print(f"   Nombre de langues: {len(result)}")
        
        if 'en-US' in result:
            print(f"   en-US trouvé: {result['en-US']}")
        if 'en' in result:
            print(f"   en trouvé: {result['en']}")
            
    except Exception as e:
        print(f"   ERREUR: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n2. Test direct du téléchargement avec notre fonction:")
    
    import tempfile
    from pathlib import Path
    
    with tempfile.TemporaryDirectory() as tmpdir:
        work_dir = Path(tmpdir)
        
        try:
            # Test avec notre fonction modifiée
            subtitle_path = provider.download_subtitles(
                url=url, 
                languages=["en", "en-US"], 
                output_dir=work_dir
            )
            
            print(f"   Résultat download_subtitles: {subtitle_path}")
            
            if subtitle_path and subtitle_path.exists():
                print(f"   Fichier créé: {subtitle_path.name} ({subtitle_path.stat().st_size} bytes)")
                content = subtitle_path.read_text(encoding='utf-8', errors='ignore')
                print(f"   Extrait: {repr(content[:150])}")
            else:
                print("   Aucun fichier créé")
                
                # Lister ce qui a été créé
                print("   Fichiers dans le répertoire:")
                for f in work_dir.iterdir():
                    print(f"     - {f.name} ({f.stat().st_size} bytes)")
                    
        except Exception as e:
            print(f"   ERREUR download_subtitles: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_parsing()