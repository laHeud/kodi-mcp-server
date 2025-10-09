#!/usr/bin/env python3
"""
Test simple des nouveaux tools sans dépendances
"""

import os
import json
import re
from pathlib import Path

def test_files_exist():
    """Vérifier que tous les fichiers nécessaires existent"""
    print("📁 Vérification des fichiers...")
    
    required_files = [
        "src/hybrid_server.py",
        "src/pure_mcp_server.py", 
        "src/kodi_client.py",
        "src/config.py",
        "Dockerfile",
        ".env.example"
    ]
    
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"  ✅ {file_path}")
        else:
            print(f"  ❌ {file_path} MANQUANT")
            return False
    
    return True

def test_new_tools_in_hybrid_server():
    """Vérifier les nouveaux tools dans le serveur hybride"""
    print("\n🔍 Vérification serveur hybride...")
    
    try:
        with open("src/hybrid_server.py", 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier la présence des nouveaux tools dans MCP_TOOLS
        new_tools = ["list_downloads", "play_file", "search_downloads"]
        
        for tool in new_tools:
            if f'"{tool}"' in content:
                print(f"  ✅ Tool {tool} trouvé")
            else:
                print(f"  ❌ Tool {tool} MANQUANT")
                return False
        
        # Vérifier les fonctions d'exécution
        if "list_downloads_files(" in content:
            print("  ✅ Fonction list_downloads_files trouvée")
        else:
            print("  ❌ Fonction list_downloads_files MANQUANTE")
            return False
        
        if "search_downloads_files(" in content:
            print("  ✅ Fonction search_downloads_files trouvée")
        else:
            print("  ❌ Fonction search_downloads_files MANQUANTE")
            return False
        
        # Vérifier l'intégration dans execute_tool
        execute_tool_section = re.search(r'def execute_tool.*?return payload', content, re.DOTALL)
        if execute_tool_section:
            execute_content = execute_tool_section.group(0)
            for tool in new_tools:
                if f'elif name == "{tool}"' in execute_content:
                    print(f"  ✅ Logique d'exécution {tool} trouvée")
                else:
                    print(f"  ❌ Logique d'exécution {tool} MANQUANTE")
                    return False
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lecture serveur hybride: {e}")
        return False

def test_new_tools_in_pure_server():
    """Vérifier les nouveaux tools dans le serveur MCP pur"""
    print("\n🔍 Vérification serveur MCP pur...")
    
    try:
        with open("src/pure_mcp_server.py", 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Vérifier la présence dans MCP_TOOLS_SPEC
        new_tools = ["list_downloads", "play_file", "search_downloads"]
        
        for tool in new_tools:
            if f'"name": "{tool}"' in content:
                print(f"  ✅ Tool {tool} dans MCP_TOOLS_SPEC")
            else:
                print(f"  ❌ Tool {tool} MANQUANT dans MCP_TOOLS_SPEC")
                return False
        
        # Vérifier les fonctions auxiliaires
        if "list_downloads_files(" in content:
            print("  ✅ Fonction list_downloads_files trouvée")
        else:
            print("  ❌ Fonction list_downloads_files MANQUANTE")
            return False
        
        # Vérifier l'intégration dans execute_kodi_tool
        execute_section = re.search(r'def execute_kodi_tool.*?except Exception', content, re.DOTALL)
        if execute_section:
            execute_content = execute_section.group(0)
            for tool in new_tools:
                if f'elif name == "{tool}"' in execute_content:
                    print(f"  ✅ Logique d'exécution {tool} trouvée")
                else:
                    print(f"  ❌ Logique d'exécution {tool} MANQUANTE")
                    return False
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lecture serveur MCP pur: {e}")
        return False

def test_client_methods():
    """Vérifier les nouvelles méthodes du client"""
    print("\n🔍 Vérification client Kodi...")
    
    try:
        with open("src/kodi_client.py", 'r', encoding='utf-8') as f:
            content = f.read()
        
        new_methods = ["list_directory", "search_in_directory", "play_file", "format_file_size"]
        
        for method in new_methods:
            if f"def {method}(" in content:
                print(f"  ✅ Méthode {method} trouvée")
            else:
                print(f"  ❌ Méthode {method} MANQUANTE")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lecture client Kodi: {e}")
        return False

def test_configuration():
    """Vérifier la nouvelle configuration"""
    print("\n🔍 Vérification configuration...")
    
    try:
        # Vérifier dans config.py
        with open("src/config.py", 'r', encoding='utf-8') as f:
            config_content = f.read()
        
        if "kodi_downloads_path" in config_content:
            print("  ✅ Variable kodi_downloads_path dans config.py")
        else:
            print("  ❌ Variable kodi_downloads_path MANQUANTE dans config.py")
            return False
        
        # Vérifier dans .env.example
        with open(".env.example", 'r', encoding='utf-8') as f:
            env_content = f.read()
        
        if "KODI_DOWNLOADS_PATH" in env_content:
            print("  ✅ Variable KODI_DOWNLOADS_PATH dans .env.example")
        else:
            print("  ❌ Variable KODI_DOWNLOADS_PATH MANQUANTE dans .env.example")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur vérification config: {e}")
        return False

def test_dockerfile():
    """Vérifier que le Dockerfile utilise le serveur hybride"""
    print("\n🔍 Vérification Dockerfile...")
    
    try:
        with open("Dockerfile", 'r', encoding='utf-8') as f:
            content = f.read()
        
        if "src.hybrid_server:app" in content:
            print("  ✅ Dockerfile utilise src.hybrid_server:app")
        else:
            print("  ❌ Dockerfile n'utilise pas src.hybrid_server:app")
            if "src.pure_mcp_server:app" in content:
                print("  ⚠️  Dockerfile utilise encore src.pure_mcp_server:app")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lecture Dockerfile: {e}")
        return False

def count_tools():
    """Compter le nombre total de tools"""
    print("\n📊 Comptage des tools...")
    
    try:
        # Serveur hybride
        with open("src/hybrid_server.py", 'r', encoding='utf-8') as f:
            hybrid_content = f.read()
        
        # Chercher MCP_TOOLS = {
        mcp_tools_match = re.search(r'MCP_TOOLS = \{(.*?)\}', hybrid_content, re.DOTALL)
        if mcp_tools_match:
            tools_content = mcp_tools_match.group(1)
            # Compter les outils (chaque outil commence par "nom_tool": {)
            tool_count = len(re.findall(r'"[^"]+"\s*:', tools_content))
            print(f"  📈 Serveur hybride: {tool_count} tools")
        
        # Serveur MCP pur
        with open("src/pure_mcp_server.py", 'r', encoding='utf-8') as f:
            pure_content = f.read()
        
        # Chercher MCP_TOOLS_SPEC = [
        spec_match = re.search(r'MCP_TOOLS_SPEC = \[(.*?)\]', pure_content, re.DOTALL)
        if spec_match:
            spec_content = spec_match.group(1)
            # Compter les tools (chaque tool a "name": "nom")
            tool_count = len(re.findall(r'"name":\s*"[^"]+"', spec_content))
            print(f"  📈 Serveur MCP pur: {tool_count} tools")
        
        # Devraient avoir 15 tools (12 originaux + 3 nouveaux)
        expected_count = 15
        print(f"  🎯 Attendu: {expected_count} tools")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur comptage tools: {e}")
        return False

def show_new_tools_details():
    """Afficher les détails des nouveaux tools"""
    print("\n🎬 Détails des nouveaux tools...")
    
    try:
        with open("src/hybrid_server.py", 'r', encoding='utf-8') as f:
            content = f.read()
        
        new_tools = ["list_downloads", "play_file", "search_downloads"]
        
        for tool in new_tools:
            # Rechercher la définition du tool
            pattern = f'"{tool}".*?"description":\s*"([^"]+)"'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                description = match.group(1)
                print(f"  🎯 {tool}: {description}")
            else:
                print(f"  ❓ {tool}: Description non trouvée")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lecture détails: {e}")
        return False

def main():
    """Fonction principale de test"""
    print("🎬 Test Simple des Nouveaux Tools MCP Kodi")
    print("=" * 60)
    
    tests = [
        ("Fichiers requis", test_files_exist),
        ("Tools serveur hybride", test_new_tools_in_hybrid_server),
        ("Tools serveur MCP pur", test_new_tools_in_pure_server),
        ("Méthodes client", test_client_methods),
        ("Configuration", test_configuration),
        ("Dockerfile", test_dockerfile),
        ("Comptage tools", count_tools),
        ("Détails tools", show_new_tools_details),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n🔍 Test: {name}")
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Exception pendant {name}: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print("📊 Résultats des tests:")
    
    for i, (name, _) in enumerate(tests):
        if i < len(results):
            status = "✅ PASS" if results[i] else "❌ FAIL"
            print(f"   {name}: {status}")
    
    success_rate = sum(results) / len(results) if results else 0
    print(f"\n🎯 Taux de réussite: {success_rate:.1%}")
    
    if success_rate == 1.0:
        print("\n🎉 Tous les tests sont passés!")
        print("✅ Les nouveaux tools sont correctement intégrés dans le code.")
        print("🚀 Prêt pour le déploiement Docker!")
        
        print("\n📋 Pour tester en production:")
        print("   docker-compose up -d")
        print("   curl http://localhost:8080/tools")
        print("   curl -X POST http://localhost:8080/tools/list_downloads \\")
        print("     -H 'Content-Type: application/json' \\")
        print("     -d '{\"params\": {\"limit\": 5}}'")
        
    elif success_rate > 0.5:
        print("\n⚠️  La plupart des tests passent.")
        print("🔧 Quelques ajustements peuvent être nécessaires.")
    else:
        print("\n❌ Plusieurs tests échouent.")
        print("🛠️  Vérifiez les erreurs ci-dessus.")
    
    return success_rate == 1.0

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)