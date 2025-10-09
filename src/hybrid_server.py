"""
Serveur hybride pour Kodi
- Endpoints REST classiques (compatibilité n8n HTTP Request)  
- Endpoint WebSocket MCP (compatible n8n MCP Client)
- SSE pour monitoring temps réel
"""

import json
import logging
import asyncio
import time
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from .config import get_settings, Settings
from .kodi_client import KodiClient

# Configuration du logger
logger = logging.getLogger(__name__)

# Instance globale des settings
settings = get_settings()

# Client Kodi global
kodi = KodiClient()

# Gestion des connexions WebSocket MCP
class MCPConnectionManager:
    def __init__(self):
        self.connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)
        logger.info(f"Client MCP WebSocket connecté, total: {len(self.connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)
        logger.info(f"Client MCP WebSocket déconnecté, total: {len(self.connections)}")
    
    async def broadcast(self, message: dict):
        """Broadcast un message vers tous les clients MCP connectés"""
        for connection in self.connections.copy():
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                self.connections.remove(connection)

mcp_manager = MCPConnectionManager()

# Gestion des connexions SSE
class SSEManager:
    def __init__(self):
        self.clients: List[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    async def connect(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self.clients.append(q)
        logger.info("Client SSE connecté, total={}", len(self.clients))
        return q

    async def disconnect(self, q: asyncio.Queue):
        async with self._lock:
            if q in self.clients:
                self.clients.remove(q)
        logger.info("Client SSE déconnecté, total={}", len(self.clients))

    async def broadcast(self, event: str, data: Any):
        payload = json.dumps({"event": event, "data": data})
        for q in list(self.clients):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning("Queue SSE pleine, évènement ignoré")

sse_manager = SSEManager()

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🎬 Démarrage du serveur hybride Kodi MCP...")
    logger.info(f"Configuration Kodi: {settings.kodi_host}:{settings.kodi_port}")
    
    # Test de connexion Kodi
    if kodi.test_connection():
        logger.info("✅ Connexion Kodi: OK")
    else:
        logger.warning("⚠️  Connexion Kodi: ÉCHEC")
    
    yield
    
    logger.info("🛑 Arrêt du serveur hybride Kodi MCP")

# Application FastAPI
app = FastAPI(
    title="Kodi MCP Hybrid Server",
    version="1.0.0",
    description="Serveur hybride pour contrôler Kodi via REST et MCP",
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

# Dépendance sécurité API KEY (facultative)
async def verify_api_key(authorization: Optional[str] = Header(default=None)) -> None:
    api_key = settings.api_key
    if api_key:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Authorization Bearer requis")
        token = authorization.split(" ", 1)[1]
        if token != api_key:
            raise HTTPException(status_code=403, detail="API Key invalide")

# Tools MCP disponibles
MCP_TOOLS = {
    "get_now_playing": {
        "description": "Get currently playing media information from Kodi",
        "parameters": {}
    },
    "player_play_pause": {
        "description": "Toggle play/pause on Kodi player",
        "parameters": {}
    },
    "player_stop": {
        "description": "Stop playback on Kodi player", 
        "parameters": {}
    },
    "set_volume": {
        "description": "Set Kodi volume level (0-100)",
        "parameters": {
            "level": {
                "type": "integer",
                "description": "Volume level (0-100)",
                "minimum": 0,
                "maximum": 100,
                "required": True
            }
        }
    },
    "navigate_menu": {
        "description": "Navigate Kodi interface menu",
        "parameters": {
            "direction": {
                "type": "string", 
                "description": "Navigation direction",
                "enum": ["up", "down", "left", "right", "select", "back"],
                "required": True
            }
        }
    },
    "search_movies": {
        "description": "Search for movies in Kodi library",
        "parameters": {
            "query": {
                "type": "string",
                "description": "Search term for movies", 
                "required": True
            }
        }
    },
    "list_recent_movies": {
        "description": "List recently added movies in Kodi library",
        "parameters": {
            "limit": {
                "type": "integer",
                "description": "Number of movies to return (default: 20)",
                "minimum": 1,
                "maximum": 100,
                "required": False,
                "default": 20
            }
        }
    },
    "list_tv_shows": {
        "description": "List all TV shows in Kodi library",
        "parameters": {}
    },
    "play_movie": {
        "description": "Play a movie by its library ID in Kodi",
        "parameters": {
            "movie_id": {
                "type": "integer",
                "description": "Movie ID in Kodi library",
                "required": True
            }
        }
    },
    "play_episode": {
        "description": "Play a TV show episode in Kodi",
        "parameters": {
            "tvshow_id": {
                "type": "integer",
                "description": "TV show ID in library",
                "required": True
            },
            "season": {
                "type": "integer",
                "description": "Season number",
                "required": True
            },
            "episode": {
                "type": "integer", 
                "description": "Episode number",
                "required": True
            }
        }
    },
    "get_library_stats": {
        "description": "Get Kodi library statistics (movies, shows, episodes count)",
        "parameters": {}
    },
    "scan_library": {
        "description": "Trigger a library scan in Kodi",
        "parameters": {
            "library_type": {
                "type": "string",
                "description": "Type of library to scan (video or audio)",
                "enum": ["video", "audio"], 
                "required": False,
                "default": "video"
            }
        }
    },
    "list_downloads": {
        "description": "List all video files in the downloads directory",
        "parameters": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of files to return (default: 50)",
                "minimum": 1,
                "maximum": 100,
                "required": False,
                "default": 50
            }
        }
    },
    "play_file": {
        "description": "Play a video file by its full path",
        "parameters": {
            "file_path": {
                "type": "string",
                "description": "Full path to the video file to play",
                "required": True
            }
        }
    },
    "search_downloads": {
        "description": "Search for files in downloads directory by name (case-insensitive)",
        "parameters": {
            "query": {
                "type": "string",
                "description": "Search term to filter files",
                "required": True
            }
        }
    },
    "find_and_play": {
        "description": "Smart search and automatic playback of the best matching file in downloads",
        "parameters": {
            "query": {
                "type": "string",
                "description": "Search term (can be partial, e.g. 'monkey', 'avengers', 'matrix')",
                "required": True
            },
            "auto_play": {
                "type": "boolean",
                "description": "Automatically play the best result (default: true)",
                "required": False,
                "default": True
            }
        }
    }
}

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

def find_and_play_files(query: str, auto_play: bool = True):
    """Recherche intelligente et lecture automatique du meilleur fichier trouvé"""
    try:
        # Utilise la nouvelle méthode de recherche intelligente du client Kodi
        return kodi.find_best_match_and_play(settings.kodi_downloads_path, query, auto_play)
    except Exception as e:
        logger.error(f"Erreur lors de la recherche intelligente: {e}")
        from .kodi_client import KodiResponse
        return KodiResponse(
            success=False,
            error=f"Erreur lors de la recherche intelligente: {e}",
            error_code="SMART_SEARCH_ERROR"
        )

def execute_tool(name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Exécute un tool et retourne le résultat formaté"""
    start = time.time()
    try:
        if name == "get_now_playing":
            res = kodi.get_now_playing()
        elif name == "player_play_pause":
            res = kodi.player_play_pause()
        elif name == "player_stop":
            res = kodi.player_stop()
        elif name == "set_volume":
            level = int(params.get("level"))
            res = kodi.set_volume(level)
        elif name == "navigate_menu":
            direction = str(params.get("direction", ""))
            res = kodi.navigate_menu(direction)
        elif name == "search_movies":
            query = str(params.get("query", "")).strip()
            res = kodi.search_movies(query)
        elif name == "list_recent_movies":
            limit = int(params.get("limit", 20))
            res = kodi.list_recent_movies(limit)
        elif name == "list_tv_shows":
            res = kodi.list_tv_shows()
        elif name == "play_movie":
            movie_id = int(params.get("movie_id"))
            res = kodi.play_movie(movie_id)
        elif name == "play_episode":
            tvshow_id = int(params.get("tvshow_id"))
            season = int(params.get("season"))
            episode = int(params.get("episode"))
            res = kodi.play_episode(tvshow_id, season, episode)
        elif name == "get_library_stats":
            res = kodi.get_library_stats()
        elif name == "scan_library":
            library_type = str(params.get("library_type", "video"))
            res = kodi.scan_library(library_type)
        elif name == "list_downloads":
            limit = int(params.get("limit", 50))
            res = list_downloads_files(limit)
        elif name == "play_file":
            file_path = str(params.get("file_path", "")).strip()
            if not file_path:
                return {"success": False, "error": "Paramètre 'file_path' manquant"}
            res = kodi.play_file(file_path)
        elif name == "search_downloads":
            query = str(params.get("query", "")).strip()
            if not query:
                return {"success": False, "error": "Paramètre 'query' manquant"}
            res = search_downloads_files(query)
        elif name == "find_and_play":
            query = str(params.get("query", "")).strip()
            if not query:
                return {"success": False, "error": "Paramètre 'query' manquant"}
            auto_play = bool(params.get("auto_play", True))
            res = find_and_play_files(query, auto_play)
        else:
            return {"success": False, "error": f"Tool inconnu: {name}"}

        duration = round((time.time() - start) * 1000)
        payload = {
            "tool": name,
            "success": res.success,
            "data": res.data,
            "error": res.error,
            "error_code": res.error_code,
            "duration_ms": duration,
        }
        return payload
    except Exception as e:
        logger.exception(f"Erreur d'exécution du tool {name}")
        return {"success": False, "error": str(e)}

# === ENDPOINTS REST CLASSIQUES ===

@app.get("/health")
async def health() -> Dict[str, Any]:
    """Health check pour monitoring"""
    ok = True
    kodi_ok = False
    try:
        ping = kodi.ping()
        kodi_ok = ping.success and (ping.data == "pong" or ping.data == {"ping": "pong"} or ping.data == "OK")
    except Exception:
        kodi_ok = False
    ok = ok and kodi_ok
    return {"status": "ok" if ok else "degraded", "kodi": "ok" if kodi_ok else "down"}

@app.get("/tools")
async def list_tools() -> Dict[str, Any]:
    """Liste et documentation des tools disponibles"""
    return {
        "server": settings.mcp_server_name,
        "transport": "http+sse+websocket",
        "tools": MCP_TOOLS,
    }

@app.post("/tools/{tool_name}")
async def call_tool_rest(tool_name: str, request: Request, _=Depends(verify_api_key)) -> JSONResponse:
    """Exécute un tool MCP via POST JSON"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    params = body.get("params", {}) if isinstance(body, dict) else {}

    if tool_name not in MCP_TOOLS:
        raise HTTPException(status_code=404, detail="Tool inconnu")

    result = execute_tool(tool_name, params)

    # Broadcast vers SSE et WebSocket
    await sse_manager.broadcast("tool_executed", {"tool": tool_name, "result": result})
    await mcp_manager.broadcast({
        "jsonrpc": "2.0",
        "method": "notifications/tools/tool_executed",
        "params": {"tool": tool_name, "result": result}
    })

    status = 200 if result.get("success") else 400
    return JSONResponse(status_code=status, content=result)

@app.get("/sse")
async def sse_endpoint(_=Depends(verify_api_key)) -> EventSourceResponse:
    """Flux SSE pour recevoir les évènements serveur et résultats des tools"""
    client_queue = await sse_manager.connect()

    async def event_generator():
        # message initial
        initial = {
            "server": settings.mcp_server_name,
            "message": "SSE connecté", 
            "tools": list(MCP_TOOLS.keys()),
        }
        yield json.dumps({"event": "ready", "data": initial})

        try:
            while True:
                try:
                    payload = await asyncio.wait_for(client_queue.get(), timeout=15.0)
                    yield payload
                except asyncio.TimeoutError:
                    # heartbeat
                    yield json.dumps({"event": "heartbeat", "data": {"ts": time.time()}})
        except asyncio.CancelledError:
            await sse_manager.disconnect(client_queue)
            raise

    return EventSourceResponse(event_generator())

# === ENDPOINT MCP SSE RACINE (pour n8n) ===

@app.post("/")
async def mcp_jsonrpc_endpoint(request: Request):
    """
    Endpoint racine pour les requêtes JSON-RPC MCP
    Compatible avec n8n MCP Client
    """
    try:
        body = await request.json()
        logger.info(f"Requête MCP JSON-RPC: {body.get('method', 'unknown')}")
        
        method = body.get("method")
        msg_id = body.get("id")
        params = body.get("params", {})
        
        # Initialize - Initialisation du serveur MCP
        if method == "initialize":
            return JSONResponse(content={
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
                        "name": settings.mcp_server_name,
                        "version": "1.0.0"
                    }
                }
            })
        
        # Liste des tools
        elif method == "tools/list":
            tools_spec = []
            for name, info in MCP_TOOLS.items():
                # Convertir le format hybride vers le format MCP standard
                properties = {}
                required = []
                
                for param_name, param_info in info.get("parameters", {}).items():
                    properties[param_name] = {
                        "type": param_info.get("type", "string"),
                        "description": param_info.get("description", "")
                    }
                    if param_info.get("enum"):
                        properties[param_name]["enum"] = param_info["enum"]
                    if param_info.get("minimum"):
                        properties[param_name]["minimum"] = param_info["minimum"]
                    if param_info.get("maximum"):
                        properties[param_name]["maximum"] = param_info["maximum"]
                    
                    if param_info.get("required", False):
                        required.append(param_name)
                
                tools_spec.append({
                    "name": name,
                    "description": info["description"],
                    "inputSchema": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                })
            
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": tools_spec
                }
            })
        
        # Exécution d'un tool
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if tool_name not in MCP_TOOLS:
                return JSONResponse(content={
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"Tool inconnu: {tool_name}"
                    }
                })
            
            # Exécuter le tool
            result = execute_tool(tool_name, arguments)
            
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ]
                }
            })
        
        # Méthode non supportée
        else:
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Méthode non supportée: {method}"
                }
            })
            
    except Exception as e:
        logger.error(f"Erreur traitement requête MCP: {e}")
        return JSONResponse(content={
            "jsonrpc": "2.0",
            "id": body.get("id") if 'body' in locals() else None,
            "error": {
                "code": -32603,
                "message": "Erreur interne",
                "data": str(e)
            }
        }, status_code=500)

@app.get("/")
async def mcp_sse_endpoint():
    """
    Endpoint SSE racine pour le protocole MCP
    Compatible avec n8n MCP Client
    """
    client_queue = await sse_manager.connect()
    
    async def mcp_sse_generator():
        # Message d'initialisation automatique
        init_message = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {
                "server": settings.mcp_server_name,
                "capabilities": ["tools"],
                "tools_count": len(MCP_TOOLS)
            }
        }
        yield f"data: {json.dumps(init_message)}\n\n"
        
        try:
            while True:
                try:
                    # Attendre des messages avec timeout
                    payload = await asyncio.wait_for(client_queue.get(), timeout=30.0)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat pour maintenir la connexion
                    heartbeat = {
                        "jsonrpc": "2.0",
                        "method": "notifications/heartbeat",
                        "params": {"timestamp": time.time()}
                    }
                    yield f"data: {json.dumps(heartbeat)}\n\n"
        except asyncio.CancelledError:
            await sse_manager.disconnect(client_queue)
            raise
        except Exception as e:
            logger.error(f"Erreur dans le générateur SSE MCP: {e}")
            await sse_manager.disconnect(client_queue)
            raise
    
    return EventSourceResponse(mcp_sse_generator())

# === ENDPOINT WEBSOCKET MCP ===

@app.websocket("/mcp")
async def mcp_websocket(websocket: WebSocket):
    """
    Endpoint WebSocket pour le protocole MCP
    Compatible avec le node MCP Client de n8n
    """
    await mcp_manager.connect(websocket)
    
    # Message d'initialisation MCP
    await websocket.send_text(json.dumps({
        "jsonrpc": "2.0",
        "id": "init",
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
    }))
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Traitement des requêtes MCP JSON-RPC
            if message.get("method") == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": {
                        "tools": [
                            {
                                "name": name,
                                "description": info["description"],
                                "inputSchema": {
                                    "type": "object",
                                    "properties": info.get("parameters", {}),
                                    "required": [
                                        param_name for param_name, param_info in info.get("parameters", {}).items()
                                        if param_info.get("required", False)
                                    ]
                                }
                            }
                            for name, info in MCP_TOOLS.items()
                        ]
                    }
                }
                await websocket.send_text(json.dumps(response))
            
            elif message.get("method") == "tools/call":
                tool_name = message.get("params", {}).get("name")
                arguments = message.get("params", {}).get("arguments", {})
                
                if tool_name in MCP_TOOLS:
                    result = execute_tool(tool_name, arguments)
                    response = {
                        "jsonrpc": "2.0", 
                        "id": message.get("id"),
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(result, indent=2)
                                }
                            ]
                        }
                    }
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": message.get("id"),
                        "error": {
                            "code": -32601,
                            "message": f"Tool non trouvé: {tool_name}"
                        }
                    }
                
                await websocket.send_text(json.dumps(response))
            
            else:
                # Méthode non supportée
                response = {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {
                        "code": -32601,
                        "message": f"Méthode non supportée: {message.get('method')}"
                    }
                }
                await websocket.send_text(json.dumps(response))
                
    except WebSocketDisconnect:
        mcp_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Erreur WebSocket MCP: {e}")
        mcp_manager.disconnect(websocket)

# Gestion d'erreurs globale
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Erreur non gérée: {}", exc)
    return JSONResponse(status_code=500, content={"detail": "Erreur interne du serveur"})

# Point d'entrée pour uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.hybrid_server:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )