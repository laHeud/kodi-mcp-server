"""
Serveur MCP pur pour Kodi
Implémente exactement le protocole MCP standard : JSON-RPC 2.0 via SSE
Compatible avec le node MCP Client de n8n
"""

import json
import logging
import asyncio
import time
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from starlette.responses import Response

from .config import get_settings
from .kodi_client import KodiClient

# Configuration du logger
logger = logging.getLogger(__name__)

# Instance globale des settings
settings = get_settings()

# Client Kodi global
kodi = KodiClient()

# Gestionnaire des connexions SSE MCP
class MCPSSEManager:
    def __init__(self):
        self.clients: List[asyncio.Queue] = []
        self.request_handlers = {}
    
    async def add_client(self) -> asyncio.Queue:
        client_queue = asyncio.Queue()
        self.clients.append(client_queue)
        logger.info(f"Client MCP connecté, total: {len(self.clients)}")
        return client_queue
    
    def remove_client(self, client_queue: asyncio.Queue):
        if client_queue in self.clients:
            self.clients.remove(client_queue)
        logger.info(f"Client MCP déconnecté, total: {len(self.clients)}")
    
    async def send_to_client(self, client_queue: asyncio.Queue, message: dict):
        """Envoie un message JSON-RPC à un client spécifique"""
        try:
            await client_queue.put(json.dumps(message))
        except Exception as e:
            logger.error(f"Erreur envoi message MCP: {e}")

mcp_manager = MCPSSEManager()

# Spécification des tools MCP selon le standard
MCP_TOOLS_SPEC = [
    {
        "name": "getnowplaying",
        "description": "Récupère ce qui joue actuellement sur Kodi (titre, durée, temps écoulé, etc.)",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "playerplaypause",
        "description": "Toggle play/pause sur le player actif de Kodi",
        "inputSchema": {
            "type": "object", 
            "properties": {},
            "required": []
        }
    },
    {
        "name": "playerstop",
        "description": "Arrêter la lecture sur Kodi",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "setvolume",
        "description": "Régler le volume de Kodi (0-100)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "level": {
                    "type": "integer",
                    "title": "Level",
                    "description": "Niveau de volume (0-100)",
                    "minimum": 0,
                    "maximum": 100
                }
            },
            "required": ["level"]
        }
    },
    {
        "name": "navigatemenu",
        "description": "Navigation dans l'interface de Kodi",
        "inputSchema": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "title": "Direction",
                    "description": "Direction de navigation",
                    "enum": ["up", "down", "left", "right", "select", "back"]
                }
            },
            "required": ["direction"]
        }
    },
    {
        "name": "searchmovies",
        "description": "Chercher des films dans la bibliothèque Kodi",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "title": "Query",
                    "description": "Terme de recherche"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "listrecentmovies",
        "description": "Liste les films récemment ajoutés à Kodi",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "title": "Limit",
                    "description": "Nombre de films à retourner (défaut: 20)",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20
                }
            },
            "required": []
        }
    },
    {
        "name": "listtvshows",
        "description": "Liste toutes les séries TV dans Kodi",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "playmovie",
        "description": "Lancer un film par son ID dans Kodi",
        "inputSchema": {
            "type": "object",
            "properties": {
                "movieid": {
                    "type": "integer",
                    "title": "Movie ID",
                    "description": "ID du film dans la bibliothèque Kodi",
                    "minimum": 1
                }
            },
            "required": ["movieid"]
        }
    },
    {
        "name": "playepisode",
        "description": "Lancer un épisode de série dans Kodi",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tvshowid": {
                    "type": "integer",
                    "title": "TV Show ID",
                    "description": "ID de la série",
                    "minimum": 1
                },
                "season": {
                    "type": "integer",
                    "title": "Season",
                    "description": "Numéro de saison",
                    "minimum": 1
                },
                "episode": {
                    "type": "integer",
                    "title": "Episode",
                    "description": "Numéro d'épisode",
                    "minimum": 1
                }
            },
            "required": ["tvshowid", "season", "episode"]
        }
    },
    {
        "name": "getlibrarystats",
        "description": "Récupérer les statistiques de la bibliothèque Kodi (films, séries, épisodes, musique)",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "scanlibrary",
        "description": "Lancer un scan de la bibliothèque Kodi",
        "inputSchema": {
            "type": "object",
            "properties": {
                "librarytype": {
                    "type": "string",
                    "title": "Library Type",
                    "description": "Type de bibliothèque à scanner",
                    "enum": ["video", "audio"],
                    "default": "video"
                }
            },
            "required": []
        }
    },
    {
        "name": "listdownloads",
        "description": "Liste tous les fichiers vidéo dans le dossier downloads (récursif)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "title": "Limit",
                    "description": "Nombre de fichiers à retourner (défaut: 50)",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 50
                }
            },
            "required": []
        }
    },
    {
        "name": "playfile",
        "description": "Lance un fichier vidéo par son chemin complet",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filepath": {
                    "type": "string",
                    "title": "File Path",
                    "description": "Chemin complet du fichier vidéo à lancer"
                }
            },
            "required": ["filepath"]
        }
    },
    {
        "name": "searchdownloads",
        "description": "Cherche des fichiers dans le dossier downloads par nom (insensible à la casse)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "title": "Query",
                    "description": "Terme de recherche pour filtrer les fichiers"
                }
            },
            "required": ["query"]
        }
    }
]

def list_downloads_files(limit: int = 50):
    """Liste les fichiers dans le dossier downloads en utilisant les méthodes du client Kodi"""
    try:
        # Utilise la nouvelle méthode du client Kodi
        return kodi.list_directory(settings.kodi_downloads_path, limit)
    except Exception as e:
        logger.error(f"Erreur lors de la liste des downloads: {e}")
        from .kodi_client import KodiResponse
        return KodiResponse(
            success=False,
            error=f"Erreur lors de la liste des downloads: {e}",
            error_code="DOWNLOAD_LIST_ERROR"
        )

def search_downloads_files(query: str):
    """Recherche des fichiers dans le dossier downloads"""
    try:
        # Utilise la nouvelle méthode de recherche du client Kodi
        return kodi.search_in_directory(settings.kodi_downloads_path, query)
    except Exception as e:
        logger.error(f"Erreur lors de la recherche dans downloads: {e}")
        from .kodi_client import KodiResponse
        return KodiResponse(
            success=False,
            error=f"Erreur lors de la recherche dans downloads: {e}",
            error_code="DOWNLOAD_SEARCH_ERROR"
        )

def execute_kodi_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Exécute un tool Kodi et retourne le résultat MCP"""
    logger.info(f"Exécution tool MCP: {name} avec arguments: {arguments}")
    
    try:
        if name == "getnowplaying":
            res = kodi.get_now_playing()
        elif name == "playerplaypause":
            res = kodi.player_play_pause()
        elif name == "playerstop":
            res = kodi.player_stop()
        elif name == "setvolume":
            level = arguments.get("level")
            if level is None:
                return {
                    "success": False,
                    "error": "Paramètre 'level' manquant"
                }
            res = kodi.set_volume(int(level))
        elif name == "navigatemenu":
            direction = arguments.get("direction")
            if direction is None:
                return {
                    "success": False,
                    "error": "Paramètre 'direction' manquant"
                }
            res = kodi.navigate_menu(str(direction))
        elif name == "searchmovies":
            query = arguments.get("query")
            if query is None:
                return {
                    "success": False,
                    "error": "Paramètre 'query' manquant"
                }
            res = kodi.search_movies(str(query))
        elif name == "listrecentmovies":
            limit = arguments.get("limit", 20)
            res = kodi.list_recent_movies(int(limit))
        elif name == "listtvshows":
            res = kodi.list_tv_shows()
        elif name == "playmovie":
            movie_id = arguments.get("movieid")
            if movie_id is None:
                return {
                    "success": False,
                    "error": "Paramètre 'movieid' manquant"
                }
            res = kodi.play_movie(int(movie_id))
        elif name == "playepisode":
            tvshow_id = arguments.get("tvshowid")
            season = arguments.get("season")
            episode = arguments.get("episode")
            
            if any(x is None for x in [tvshow_id, season, episode]):
                return {
                    "success": False,
                    "error": "Paramètres 'tvshowid', 'season', 'episode' requis"
                }
            res = kodi.play_episode(int(tvshow_id), int(season), int(episode))
        elif name == "getlibrarystats":
            res = kodi.get_library_stats()
        elif name == "scanlibrary":
            library_type = arguments.get("librarytype", "video")
            res = kodi.scan_library(str(library_type))
        elif name == "listdownloads":
            limit = arguments.get("limit", 50)
            res = list_downloads_files(int(limit))
        elif name == "playfile":
            file_path = arguments.get("filepath")
            if file_path is None:
                return {
                    "success": False,
                    "error": "Paramètre 'filepath' manquant"
                }
            res = kodi.play_file(str(file_path))
        elif name == "searchdownloads":
            query = arguments.get("query")
            if query is None:
                return {
                    "success": False,
                    "error": "Paramètre 'query' manquant"
                }
            res = search_downloads_files(str(query))
        else:
            return {
                "success": False,
                "error": f"Tool inconnu: {name}"
            }
        
        # Formatage du résultat selon MCP
        if res.success:
            return {
                "success": True,
                "data": res.data,
                "tool": name
            }
        else:
            return {
                "success": False,
                "error": res.error,
                "error_code": res.error_code,
                "tool": name
            }
            
    except Exception as e:
        logger.exception(f"Erreur lors de l'exécution du tool {name}")
        return {
            "success": False,
            "error": str(e),
            "tool": name
        }

def handle_jsonrpc_request(message: dict) -> dict:
    """Traite une requête JSON-RPC MCP et retourne la réponse"""
    method = message.get("method")
    msg_id = message.get("id")
    params = message.get("params", {})
    
    # Initialize - Initialisation du serveur MCP
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {
                        "listChanged": True
                    }
                },
                "serverInfo": {
                    "name": "kodi-controller", 
                    "version": "1.0.0"
                }
            }
        }
    
    # Tools/list - Liste des tools disponibles
    elif method == "tools/list":
        # Validation des tools avant envoi
        validated_tools = []
        for tool in MCP_TOOLS_SPEC:
            # Vérifier que toutes les propriétés requises sont présentes
            if not tool.get("name"):
                logger.error(f"Tool sans nom détecté: {tool}")
                continue
            if not tool.get("description"):
                logger.error(f"Tool {tool.get('name')} sans description")
                continue
            if not tool.get("inputSchema"):
                logger.error(f"Tool {tool.get('name')} sans inputSchema")
                continue
            
            # Nettoyer le tool de toute propriété None/undefined
            clean_tool = {
                "name": str(tool["name"]),
                "description": str(tool["description"]),
                "inputSchema": tool["inputSchema"]
            }
            
            validated_tools.append(clean_tool)
        
        # Debug pour Langfuse
        logger.error('=== DEBUG MCP TOOLS ===')
        for idx, tool in enumerate(validated_tools):
            logger.error(f"Tool {idx}: {json.dumps(tool, indent=2, ensure_ascii=False)}")
        logger.error('=======================')
        
        logger.info(f"Retour de {len(validated_tools)} tools validés")
        
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": validated_tools
            }
        }
    
    # Tools/call - Exécution d'un tool
    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not tool_name:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32602,
                    "message": "Paramètre 'name' manquant"
                }
            }
        
        # Vérifier que le tool existe
        if not any(tool["name"] == tool_name for tool in MCP_TOOLS_SPEC):
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Tool non trouvé: {tool_name}"
                }
            }
        
        # Exécuter le tool
        result = execute_kodi_tool(tool_name, arguments)
        
        if result.get("success"):
            # Succès - format MCP content
            content_text = json.dumps(result, indent=2)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": content_text
                        }
                    ]
                }
            }
        else:
            # Erreur tool
            return {
                "jsonrpc": "2.0", 
                "id": msg_id,
                "error": {
                    "code": -32603,
                    "message": result.get("error", "Erreur lors de l'exécution du tool"),
                    "data": result
                }
            }
    
    # Méthode non supportée
    else:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": -32601,
                "message": f"Méthode non supportée: {method}"
            }
        }

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🎬 Démarrage du serveur MCP pur...")
    logger.info(f"Configuration Kodi: {settings.kodi_host}:{settings.kodi_port}")
    
    # Test de connexion Kodi
    if kodi.test_connection():
        logger.info("✅ Connexion Kodi: OK")
    else:
        logger.warning("⚠️  Connexion Kodi: ÉCHEC")
    
    yield
    
    logger.info("🛑 Arrêt du serveur MCP pur")

# Application FastAPI
app = FastAPI(
    title="Kodi MCP Server (Standard)",
    version="1.0.0",
    description="Serveur MCP pur pour Kodi - JSON-RPC 2.0 via SSE",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/")
async def mcp_endpoint(request: Request):
    """
    Endpoint principal MCP - JSON-RPC 2.0 via HTTP POST
    Compatible avec les clients MCP standard
    """
    try:
        # Parse de la requête JSON-RPC
        body = await request.json()
        
        # Traitement de la requête
        response = handle_jsonrpc_request(body)
        
        # Retour de la réponse JSON-RPC
        return response
        
    except json.JSONDecodeError:
        return {
            "jsonrpc": "2.0", 
            "id": None,
            "error": {
                "code": -32700,
                "message": "Erreur de parsing JSON"
            }
        }
    except Exception as e:
        logger.exception("Erreur endpoint MCP")
        return {
            "jsonrpc": "2.0",
            "id": None, 
            "error": {
                "code": -32603,
                "message": f"Erreur interne: {str(e)}"
            }
        }

@app.get("/sse")
async def mcp_sse_endpoint(request: Request):
    """
    Endpoint SSE pour le protocole MCP
    JSON-RPC 2.0 via Server-Sent Events
    Compatible avec le node MCP Client de n8n
    """
    client_queue = await mcp_manager.add_client()
    
    async def event_generator():
        try:
            # Message d'initialisation automatique 
            init_message = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {
                            "listChanged": True
                        }
                    },
                    "serverInfo": {
                        "name": "kodi-controller",
                        "version": "1.0.0"
                    }
                }
            }
            
            # Envoi du message d'initialisation
            yield f"data: {json.dumps(init_message)}\n\n"
            
            # Boucle principale SSE
            while True:
                try:
                    # Attendre un message ou timeout pour heartbeat
                    message = await asyncio.wait_for(client_queue.get(), timeout=30.0)
                    yield f"data: {message}\n\n"
                    
                except asyncio.TimeoutError:
                    # Heartbeat MCP standard
                    heartbeat = {
                        "jsonrpc": "2.0",
                        "method": "notifications/ping",
                        "params": {
                            "timestamp": int(time.time())
                        }
                    }
                    yield f"data: {json.dumps(heartbeat)}\n\n"
                    
        except asyncio.CancelledError:
            mcp_manager.remove_client(client_queue)
            raise
        except Exception as e:
            logger.error(f"Erreur SSE MCP: {e}")
            mcp_manager.remove_client(client_queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@app.get("/health")
async def health():
    """Health check simple"""
    kodi_ok = kodi.test_connection()
    return {
        "status": "ok" if kodi_ok else "degraded",
        "kodi": "ok" if kodi_ok else "down",
        "mcp_version": "2024-11-05",
        "server": "kodi-controller"
    }

# Point d'entrée pour uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.pure_mcp_server:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )