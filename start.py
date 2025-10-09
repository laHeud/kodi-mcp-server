#!/usr/bin/env python3
"""
Script de lancement rapide pour le serveur MCP Kodi
Usage: python start.py
"""

import os
import sys
import uvicorn
from pathlib import Path

# Ajouter le répertoire src au path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def main():
    """Point d'entrée principal"""
    print("🎬 Démarrage du serveur MCP Kodi...")
    print("📂 Répertoire de travail:", os.getcwd())
    
    # Vérification du fichier .env
    env_file = Path(".env")
    if not env_file.exists():
        print("⚠️  Fichier .env manquant, copie depuis .env.example")
        if Path(".env.example").exists():
            import shutil
            shutil.copy(".env.example", ".env")
        else:
            print("❌ Fichier .env.example manquant!")
            sys.exit(1)
    
    # Import du serveur
    try:
        from src.server import app
        from src.config import settings
        
        print(f"✅ Configuration chargée:")
        print(f"   - Kodi: {settings.kodi_host}:{settings.kodi_port}")
        print(f"   - Serveur: {settings.server_host}:{settings.server_port}")
        print(f"   - Environnement: {settings.environment}")
        
        # Test de connexion Kodi optionnel
        try:
            from src.kodi_client import KodiClient
            kodi = KodiClient()
            if kodi.test_connection():
                print("✅ Connexion Kodi: OK")
            else:
                print("⚠️  Connexion Kodi: ÉCHEC (le serveur démarrera quand même)")
        except Exception as e:
            print(f"⚠️  Test connexion Kodi échoué: {e}")
        
        print(f"\n🚀 Serveur démarré sur http://{settings.server_host}:{settings.server_port}")
        print("📖 Endpoints disponibles:")
        print(f"   - Health check: http://localhost:{settings.server_port}/health")
        print(f"   - Liste tools: http://localhost:{settings.server_port}/tools")
        print(f"   - SSE stream: http://localhost:{settings.server_port}/sse")
        print("\n⏹️  Arrêter avec Ctrl+C")
        
        # Lancement du serveur
        uvicorn.run(
            app,
            host=settings.server_host,
            port=settings.server_port,
            reload=settings.environment == "development",
            log_level=settings.log_level.lower()
        )
        
    except ImportError as e:
        print(f"❌ Erreur d'import: {e}")
        print("💡 Installez les dépendances: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erreur de démarrage: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()