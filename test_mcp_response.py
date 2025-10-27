#!/usr/bin/env python3
"""
Script pour tester les réponses du serveur MCP
Vérifie que tous les tools ont les propriétés requises
"""

import requests
import json

# URL du serveur MCP
MCP_URL = "http://192.168.1.81:8081"

def test_initialize():
    """Test de l'initialisation"""
    print("🔍 Test initialize...")
    payload = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": 1
    }
    
    response = requests.post(MCP_URL, json=payload)
    result = response.json()
    
    print(f"✅ Initialize: {json.dumps(result, indent=2)}")
    return result

def test_tools_list():
    """Test de la liste des tools"""
    print("\n🔍 Test tools/list...")
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 2
    }
    
    response = requests.post(MCP_URL, json=payload)
    result = response.json()
    
    # Vérifier la structure
    if "result" in result and "tools" in result["result"]:
        tools = result["result"]["tools"]
        print(f"✅ Nombre de tools: {len(tools)}")
        
        # Vérifier chaque tool
        for i, tool in enumerate(tools):
            print(f"\n📦 Tool {i+1}: {tool.get('name', 'SANS NOM')}")
            
            # Vérifications
            issues = []
            if not tool.get("name"):
                issues.append("❌ Propriété 'name' manquante ou vide")
            elif not isinstance(tool.get("name"), str):
                issues.append(f"❌ 'name' n'est pas une string: {type(tool.get('name'))}")
            
            if not tool.get("description"):
                issues.append("❌ Propriété 'description' manquante ou vide")
            elif not isinstance(tool.get("description"), str):
                issues.append(f"❌ 'description' n'est pas une string: {type(tool.get('description'))}")
            
            if not tool.get("inputSchema"):
                issues.append("❌ Propriété 'inputSchema' manquante")
            elif not isinstance(tool.get("inputSchema"), dict):
                issues.append(f"❌ 'inputSchema' n'est pas un dict: {type(tool.get('inputSchema'))}")
            
            # Vérifier les propriétés inattendues
            expected_keys = {"name", "description", "inputSchema"}
            actual_keys = set(tool.keys())
            unexpected = actual_keys - expected_keys
            if unexpected:
                issues.append(f"⚠️  Propriétés inattendues: {unexpected}")
            
            # Vérifier les valeurs None
            for key, value in tool.items():
                if value is None:
                    issues.append(f"❌ Propriété '{key}' est None")
            
            if issues:
                print("\n".join(issues))
            else:
                print("   ✅ Tool valide")
                print(f"   - name: {tool['name']}")
                print(f"   - description: {tool['description'][:50]}...")
                print(f"   - inputSchema: {list(tool['inputSchema'].keys())}")
    else:
        print(f"❌ Réponse invalide: {json.dumps(result, indent=2)}")
    
    return result

def test_tool_call():
    """Test d'exécution d'un tool simple"""
    print("\n🔍 Test tools/call (get_now_playing)...")
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "get_now_playing",
            "arguments": {}
        },
        "id": 3
    }
    
    response = requests.post(MCP_URL, json=payload)
    result = response.json()
    
    print(f"Réponse: {json.dumps(result, indent=2)[:200]}...")
    return result

if __name__ == "__main__":
    print("🧪 Test du serveur MCP Kodi\n")
    print(f"URL: {MCP_URL}\n")
    
    try:
        # Test 1: Initialize
        test_initialize()
        
        # Test 2: Liste des tools
        test_tools_list()
        
        # Test 3: Exécution d'un tool
        test_tool_call()
        
        print("\n✅ Tests terminés!")
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Impossible de se connecter à {MCP_URL}")
        print("Vérifiez que le serveur MCP est démarré")
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
