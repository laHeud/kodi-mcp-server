#!/usr/bin/env python3
"""
Script de démarrage pour le serveur hybride Kodi MCP
"""

import sys
import os
import asyncio
import signal
from pathlib import Path

# Ajouter le répertoire src au chemin Python
sys.path.insert(0, str(Path(__file__).parent / "src"))

def main():
    """Fonction principale pour démarrer le serveur"""
    print("🎬 Démarrage du serveur hybride Kodi MCP...")
    
    try:
        # Importer les modules après avoir configuré le chemin
        import uvicorn
        from src.hybrid_server import app
        from src.config import get_settings
        
        settings = get_settings()
        
        print(f"📡 Configuration:")
        print(f"   - Host: {settings.server_host}:{settings.server_port}")
        print(f"   - Kodi: {settings.kodi_host}:{settings.kodi_port}")
        print(f"   - Downloads: {settings.kodi_downloads_path}")
        print(f"   - Mode: {settings.environment}")
        
        print("\n🚀 Démarrage du serveur...")
        print("   - Endpoints REST: /tools/{tool_name}")
        print("   - WebSocket MCP: /mcp")
        print("   - SSE Monitoring: /sse")
        print("   - Health check: /health")
        print("   - Documentation: /tools")
        
        # Démarrer le serveur uvicorn
        config = uvicorn.Config(
            app=app,
            host=settings.server_host,
            port=settings.server_port,
            reload=False,  # Pas de reload en production
            access_log=True,
            log_level="info" if settings.environment == "development" else "warning"
        )
        
        server = uvicorn.Server(config)
        
        # Gestion propre du signal d'arrêt
        def signal_handler(sig, frame):
            print("\n🛑 Arrêt du serveur demandé...")
            server.should_exit = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        print(f"\n✅ Serveur démarré sur http://{settings.server_host}:{settings.server_port}")
        print("   Ctrl+C pour arrêter")
        
        # Démarrer le serveur
        server.run()
        
    except ImportError as e:
        if "uvicorn" in str(e):
            print("❌ uvicorn n'est pas installé.")
            print("   Installez avec: pip install uvicorn")
        else:
            print(f"❌ Erreur d'import: {e}")
        return 1
        
    except Exception as e:
        print(f"❌ Erreur lors du démarrage: {e}")
        return 1
    
    print("👋 Serveur arrêté proprement")
    return 0

if __name__ == "__main__":
    sys.exit(main())