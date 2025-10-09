"""
Serveur MCP pour Kodi via FastAPI avec SSE et endpoints HTTP
- Endpoint santé: GET /health
- Endpoint listing tools: GET /tools
- Endpoint exécution tools: POST /tools/{tool_name}
- Endpoint SSE: GET /sse (Server-Sent Events) pour suivre l'activité

Sécurité: API Key optionnelle via en-tête Authorization: Bearer <API_KEY>
Logging: loguru + structlog
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from .config import get_settings, Settings
from .kodi_client import KodiClient

# Configuration de logging de base
from loguru import logger
import structlog


# Initialisation structlog pour un format json en production
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]
)

app = FastAPI(title="Kodi MCP Server", version="1.0.0")

settings = get_settings()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gestion des connexions SSE: chaque client reçoit sa propre queue
class SSEManager:
    def __init__(self) -> None:
        self.clients: List[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    async def connect(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self.clients.append(q)
        logger.info("Client SSE connecté, total={}", len(self.clients))
        return q

    async def disconnect(self, q: asyncio.Queue) -> None:
        async with self._lock:
            if q in self.clients:
                self.clients.remove(q)
        logger.info("Client SSE déconnecté, total={}", len(self.clients))

    async def broadcast(self, event: str, data: Any) -> None:
        payload = json.dumps({"event": event, "data": data})
        for q in list(self.clients):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning("Queue SSE pleine, évènement ignoré")

sse_manager = SSEManager()

# Dépendance sécurité API KEY (facultative si non définie)
async def verify_api_key(authorization: Optional[str] = Header(default=None)) -> None:
    api_key = settings.api_key
    if api_key:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Authorization Bearer requis")
        token = authorization.split(" ", 1)[1]
        if token != api_key:
            raise HTTPException(status_code=403, detail="API Key invalide")


# Kodi client global
kodi = KodiClient()

# Définition des tools MCP et mapping vers le client Kodi
TOOLS_DOC: Dict[str, Dict[str, Any]] = {
    "get_now_playing": {
        "description": "Récupère ce qui joue actuellement (titre, durée, temps écoulé, etc.)",
        "params": {}
    },
    "player_play_pause": {
        "description": "Toggle play/pause",
        "params": {}
    },
    "player_stop": {
        "description": "Arrêter la lecture",
        "params": {}
    },
    "set_volume": {
        "description": "Régler le volume",
        "params": {"level": "int (0-100)"}
    },
    "navigate_menu": {
        "description": "Naviguer dans le menu Kodi",
        "params": {"direction": "string: up|down|left|right|select|back"}
    },
    "search_movies": {
        "description": "Chercher des films",
        "params": {"query": "string"}
    },
    "list_recent_movies": {
        "description": "Liste les 20 derniers films ajoutés",
        "params": {"limit": "int (optionnel, défaut 20)"}
    },
    "list_tv_shows": {
        "description": "Liste toutes les séries",
        "params": {}
    },
    "play_movie": {
        "description": "Lancer un film",
        "params": {"movie_id": "int"}
    },
    "play_episode": {
        "description": "Lancer un épisode",
        "params": {"tvshow_id": "int", "season": "int", "episode": "int"}
    },
    "get_library_stats": {
        "description": "Statistiques (nb films, séries, épisodes, musique)",
        "params": {}
    },
    "scan_library": {
        "description": "Lancer un scan de la bibliothèque",
        "params": {"library_type": "string: video|audio (optionnel, défaut video)"}
    },
}


def execute_tool(name: str, params: Dict[str, Any]) -> Dict[str, Any]:
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
        logger.exception("Erreur d'exécution du tool {}", name)
        return {"success": False, "error": str(e)}


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
        "transport": "http+sse",
        "tools": TOOLS_DOC,
    }


@app.post("/tools/{tool_name}")
async def call_tool(tool_name: str, request: Request, _=Depends(verify_api_key)) -> JSONResponse:
    """
    Exécute un tool MCP via POST JSON
    Body: { "params": { ... } }
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    params = body.get("params", {}) if isinstance(body, dict) else {}

    if tool_name not in TOOLS_DOC:
        raise HTTPException(status_code=404, detail="Tool inconnu")

    result = execute_tool(tool_name, params)

    # Broadcast SSE
    await sse_manager.broadcast("tool_executed", {"tool": tool_name, "result": result})

    status = 200 if result.get("success") else 400
    return JSONResponse(status_code=status, content=result)


@app.get("/sse")
async def sse_endpoint(_=Depends(verify_api_key)) -> EventSourceResponse:
    """
    Flux SSE pour recevoir les évènements serveur et résultats des tools
    Envoyé en JSON sous forme { "event": <nom>, "data": <payload> }
    """
    client_queue = await sse_manager.connect()

    async def event_generator() -> AsyncIterator[str]:
        # message initial
        initial = {
            "server": settings.mcp_server_name,
            "message": "SSE connecté",
            "tools": list(TOOLS_DOC.keys()),
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
            # Déconnexion
            await sse_manager.disconnect(client_queue)
            raise

    return EventSourceResponse(event_generator())


# Gestion d'erreurs globale
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Erreur non gérée: {}", exc)
    return JSONResponse(status_code=500, content={"detail": "Erreur interne du serveur"})


# Point d'entrée local (uvicorn)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.server:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
