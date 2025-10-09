#!/usr/bin/env python3
"""
Script de lancement pour le serveur MCP standard
Usage: python start_mcp.py
"""

import asyncio
import sys
from pathlib import Path

# Ajouter le répertoire src au path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def main():
    """Point d'entrée principal pour le serveur MCP"""
    print("🎬 Démarrage du serveur MCP Kodi (protocole standard)...")
    
    try:
        from src.mcp_server import run_mcp_server
        await run_mcp_server()
    except ImportError as e:
        print(f"❌ Erreur d'import: {e}")
        print("💡 Installez les dépendances: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erreur de démarrage: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())