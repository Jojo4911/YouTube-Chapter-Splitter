"""Tests d'intégration pour le module YouTube avec de vraies URLs.

IMPORTANT: Ces tests nécessitent une connexion Internet et yt-dlp.
Ils peuvent être lents et consommer de la bande passante.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from ytsplit.providers.youtube import create_youtube_provider, YouTubeError
from ytsplit.config import Settings


# Marquer tous les tests de ce fichier comme des tests d'intégration lents
pytestmark = pytest.mark.slow


class TestYouTubeIntegration:
    """Tests d'intégration avec de vraies URLs YouTube."""
    
    @pytest.fixture
    def temp_settings(self):
        """Settings avec répertoires temporaires."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            yield Settings(
                work_dir=temp_path / "cache",
                out_dir=temp_path / "output",
                yt_dlp_format="worst[height<=360]",  # Qualité basse pour les tests
                video_format="mp4"
            )
    
    @pytest.fixture
    def provider(self, temp_settings):
        """Provider YouTube avec settings temporaires."""
        return create_youtube_provider(temp_settings)
    
    def test_get_info_real_video_with_chapters(self, provider):
        """Test avec une vraie vidéo qui a des chapitres."""
        # URL d'une vidéo courte avec des chapitres (exemple)
        # Note: Utiliser une vidéo publique stable pour les tests
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll - vidéo stable
        
        try:
            meta = provider.get_video_info(url)
            
            # Vérifications basiques
            assert meta.video_id == "dQw4w9WgXcQ"
            assert meta.title is not None
            assert len(meta.title) > 0
            assert meta.duration_s > 0
            assert len(meta.chapters) >= 1  # Au moins un chapitre (la vidéo entière)
            assert meta.url == url
            
            # Vérifier que les chapitres sont cohérents
            for chapter in meta.chapters:
                assert chapter.start_s >= 0
                assert chapter.end_s > chapter.start_s
                assert chapter.end_s <= meta.duration_s
                assert len(chapter.title) > 0
            
            print(f"✅ Vidéo trouvée: {meta.title} ({meta.duration_s:.1f}s)")
            print(f"   📚 {len(meta.chapters)} chapitre(s)")
            for ch in meta.chapters:
                print(f"      {ch.index:2d}. {ch.title} ({ch.start_s:.1f}s - {ch.end_s:.1f}s)")
                
        except YouTubeError as e:
            pytest.skip(f"Erreur YouTube (connexion/disponibilité): {e}")
    
    def test_get_info_nonexistent_video(self, provider):
        """Test avec une vidéo qui n'existe pas."""
        # ID valide mais vidéo inexistante
        fake_url = "https://www.youtube.com/watch?v=nonexistent"
        
        with pytest.raises(YouTubeError):
            provider.get_video_info(fake_url)
    
    def test_validate_various_youtube_urls(self, provider):
        """Test de validation avec différents formats d'URL YouTube."""
        valid_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s",
        ]
        
        for url in valid_urls:
            assert provider.validate_youtube_url(url) == True, f"URL devrait être valide: {url}"
    
    @pytest.mark.slow
    def test_download_small_video(self, provider):
        """Test de téléchargement d'une petite vidéo."""
        # Utiliser une vidéo très courte pour minimiser le temps et la bande passante
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        try:
            # Télécharger
            video_file = provider.download_video(url)
            
            # Vérifications
            assert video_file.exists()
            assert video_file.stat().st_size > 0
            assert video_file.suffix in ['.mp4', '.mkv', '.webm']
            
            print(f"✅ Vidéo téléchargée: {video_file}")
            print(f"   📁 Taille: {video_file.stat().st_size / 1024:.1f} KB")
            
        except YouTubeError as e:
            pytest.skip(f"Erreur de téléchargement: {e}")
    
    def test_process_video_complete_workflow(self, provider):
        """Test du workflow complet : métadonnées + téléchargement."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        
        try:
            meta, video_file = provider.process_video(url)
            
            # Vérifier les métadonnées
            assert meta.video_id == "dQw4w9WgXcQ"
            assert len(meta.chapters) >= 1
            
            # Vérifier le fichier
            assert video_file.exists()
            assert video_file.stat().st_size > 0
            
            print(f"✅ Workflow complet réussi:")
            print(f"   📹 {meta.title}")
            print(f"   📚 {len(meta.chapters)} chapitre(s)")
            print(f"   📁 {video_file} ({video_file.stat().st_size / 1024:.1f} KB)")
            
            # Test de cache - deuxième appel ne doit pas retélécharger
            meta2, video_file2 = provider.process_video(url, force_redownload=False)
            assert video_file == video_file2
            assert meta.video_id == meta2.video_id
            
        except YouTubeError as e:
            pytest.skip(f"Erreur de traitement: {e}")


def run_integration_tests():
    """Fonction utilitaire pour lancer les tests d'intégration manuellement."""
    print("🧪 Lancement des tests d'intégration YouTube...")
    print("⚠️  Ces tests nécessitent Internet et peuvent prendre du temps.\n")
    
    # Créer un provider temporaire
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        settings = Settings(
            work_dir=temp_path / "cache",
            out_dir=temp_path / "output",
            yt_dlp_format="worst[height<=360]",
            video_format="mp4"
        )
        
        provider = create_youtube_provider(settings)
        test_instance = TestYouTubeIntegration()
        
        try:
            # Test 1: Info vidéo
            print("1️⃣ Test extraction métadonnées...")
            test_instance.test_get_info_real_video_with_chapters(provider)
            
            # Test 2: Validation URLs
            print("\n2️⃣ Test validation URLs...")
            test_instance.test_validate_various_youtube_urls(provider)
            
            # Test 3: Téléchargement (optionnel - commenté pour éviter le téléchargement)
            # print("\n3️⃣ Test téléchargement...")
            # test_instance.test_download_small_video(provider)
            
            print("\n✅ Tous les tests d'intégration sont passés !")
            
        except Exception as e:
            print(f"\n❌ Erreur lors des tests: {e}")
            raise


if __name__ == "__main__":
    run_integration_tests()