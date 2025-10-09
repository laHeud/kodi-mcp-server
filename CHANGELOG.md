# Changelog

Toutes les modifications notables de ce projet seront documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2024-12-19

### ✨ Ajouté
- **3 nouveaux tools MCP** pour la gestion des fichiers downloads :
  - `list_downloads` : Liste récursive des fichiers vidéo dans le dossier downloads
  - `play_file` : Lance directement un fichier vidéo par son chemin complet
  - `search_downloads` : Recherche insensible à la casse dans les fichiers downloads
- **Serveur hybride** (`src/hybrid_server.py`) avec triple support :
  - Endpoints REST classiques (`/tools/{tool_name}`)
  - WebSocket MCP (`/mcp`) compatible n8n MCP Client
  - SSE monitoring temps réel (`/sse`)
- **Nouvelles méthodes client Kodi** :
  - `list_directory()` : Navigation récursive dans les dossiers
  - `search_in_directory()` : Recherche de fichiers par nom
  - `play_file()` : Lecture directe de fichiers via chemin
  - `format_file_size()` : Formatage lisible des tailles de fichier
- **Configuration étendue** :
  - Variable `KODI_DOWNLOADS_PATH` pour le dossier de téléchargements
  - Support des formats vidéo : `.mkv`, `.mp4`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`, `.m4v`

### 🔧 Modifié
- **Dockerfile** : Utilise maintenant `src.hybrid_server:app` au lieu de `src.pure_mcp_server:app`
- **Schémas MCP** : Ajout de `inputType` pour compatibilité n8n optimisée
- **Architecture** : Le serveur hybride devient le serveur principal, MCP pur conservé pour compatibilité
- **Documentation** : README et guides mis à jour avec les nouveaux tools

### 🏗️ Infrastructure
- **Scripts de test** : Nouveau script `test_server.py` pour validation syntaxique
- **Script de démarrage** : Nouveau `start_server.py` pour démarrage local simplifié
- **Guide de démarrage rapide** : Nouveau `QUICK_START.md` pour installation rapide

### 🔄 Compatibilité
- **Rétrocompatibilité** : Tous les 12 tools existants restent inchangés
- **Serveur MCP pur** : Conservé en parallèle pour compatibilité stricte MCP
- **Endpoints existants** : Aucune modification des URLs et formats de réponse

### 📁 Structure de fichiers
```
src/
├── hybrid_server.py    # 🆕 Serveur principal hybride
├── pure_mcp_server.py  # ✅ Serveur MCP pur (conservé)
├── kodi_client.py      # 🔧 Méthodes étendues pour downloads
└── config.py           # 🔧 Nouvelle variable KODI_DOWNLOADS_PATH

test_server.py          # 🆕 Script de test syntaxique
start_server.py         # 🆕 Script de démarrage local
QUICK_START.md          # 🆕 Guide de démarrage rapide
```

### 🧪 Tests
- **Validation syntaxique** : Tous les fichiers Python passent les tests AST
- **Intégration** : Nouveaux tools testés avec client Kodi mock
- **Configuration** : Variables d'environnement validées

## [1.0.0] - 2024-12-18

### ✨ Ajouté - Version initiale
- **12 tools MCP** pour contrôle complet de Kodi
- **Transport HTTP + SSE** compatible n8n
- **Authentification** via API Key optionnelle
- **Docker** avec docker-compose prêt pour production
- **Monitoring** : Health checks et logs structurés
- **Gestion d'erreurs** robuste avec retry automatique
- **Documentation** complète avec exemples n8n

### 🎯 Tools MCP v1.0.0
- `get_now_playing` : Récupération du média en cours
- `player_play_pause` : Toggle lecture/pause
- `player_stop` : Arrêt de la lecture
- `set_volume` : Contrôle du volume (0-100)
- `navigate_menu` : Navigation dans l'interface
- `search_movies` : Recherche de films
- `list_recent_movies` : Films récemment ajoutés
- `list_tv_shows` : Liste des séries TV
- `play_movie` : Lecture de film par ID
- `play_episode` : Lecture d'épisode spécifique
- `get_library_stats` : Statistiques de la bibliothèque
- `scan_library` : Scan de la bibliothèque

---

## Types de modifications

- **Ajouté** pour les nouvelles fonctionnalités
- **Modifié** pour les changements dans les fonctionnalités existantes
- **Déprécié** pour les fonctionnalités qui seront supprimées prochainement
- **Supprimé** pour les fonctionnalités supprimées maintenant
- **Corrigé** pour les corrections de bugs
- **Sécurité** en cas de vulnérabilités