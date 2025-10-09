"""
Serveur MCP standard pour Kodi
Implémente le protocole Model Context Protocol avec SSE et JSON-RPC 2.0
Compatible avec le node MCP Client de n8n
"""

import json
import logging
import asyncio
from typing import Any, Dict, List, Optional, Sequence
from dataclasses import dataclass

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.server.session import ServerSession
from mcp.server.sse import SSEServerTransport
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    Tool,
    TextContent,
    GetPromptRequest,
    GetPromptResult,
    PromptMessage,
    Prompt
)

from .kodi_client import KodiClient, KodiResponse
from .config import settings

# Configuration du logger
logger = logging.getLogger(__name__)

# Client Kodi global
kodi_client = KodiClient()

# Instance du serveur MCP
mcp_server = Server("kodi-controller")


def kodi_response_to_mcp_result(response: KodiResponse, tool_name: str) -> CallToolResult:
    """Convertit une réponse Kodi en résultat MCP"""
    if response.success:
        content = TextContent(
            type="text",
            text=json.dumps({
                "tool": tool_name,
                "success": True,
                "data": response.data
            }, indent=2)
        )
    else:
        content = TextContent(
            type="text", 
            text=json.dumps({
                "tool": tool_name,
                "success": False,
                "error": response.error,
                "error_code": response.error_code
            }, indent=2)
        )
    
    return CallToolResult(content=[content])


@mcp_server.list_tools()
async def list_tools() -> ListToolsResult:
    """Liste tous les tools MCP disponibles"""
    tools = [
        Tool(
            name="get_now_playing",
            description="Récupère ce qui joue actuellement sur Kodi (titre, durée, temps écoulé, etc.)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="player_play_pause",
            description="Toggle play/pause sur le player actif de Kodi",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="player_stop", 
            description="Arrêter la lecture sur Kodi",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="set_volume",
            description="Régler le volume de Kodi (0-100)",
            inputSchema={
                "type": "object",
                "properties": {
                    "level": {
                        "type": "integer",
                        "description": "Niveau de volume (0-100)",
                        "minimum": 0,
                        "maximum": 100
                    }
                },
                "required": ["level"]
            }
        ),
        Tool(
            name="navigate_menu",
            description="Navigation dans l'interface de Kodi",
            inputSchema={
                "type": "object", 
                "properties": {
                    "direction": {
                        "type": "string",
                        "description": "Direction de navigation",
                        "enum": ["up", "down", "left", "right", "select", "back"]
                    }
                },
                "required": ["direction"]
            }
        ),
        Tool(
            name="search_movies",
            description="Chercher des films dans la bibliothèque Kodi",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string", 
                        "description": "Terme de recherche"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="list_recent_movies",
            description="Liste les films récemment ajoutés à Kodi",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Nombre de films à retourner (défaut: 20)",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 20
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="list_tv_shows",
            description="Liste toutes les séries TV dans Kodi",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="play_movie",
            description="Lancer un film par son ID dans Kodi",
            inputSchema={
                "type": "object",
                "properties": {
                    "movie_id": {
                        "type": "integer",
                        "description": "ID du film dans la bibliothèque Kodi"
                    }
                },
                "required": ["movie_id"]
            }
        ),
        Tool(
            name="play_episode", 
            description="Lancer un épisode de série dans Kodi",
            inputSchema={
                "type": "object",
                "properties": {
                    "tvshow_id": {
                        "type": "integer",
                        "description": "ID de la série"
                    },
                    "season": {
                        "type": "integer", 
                        "description": "Numéro de saison"
                    },
                    "episode": {
                        "type": "integer",
                        "description": "Numéro d'épisode"
                    }
                },
                "required": ["tvshow_id", "season", "episode"]
            }
        ),
        Tool(
            name="get_library_stats",
            description="Récupérer les statistiques de la bibliothèque Kodi (films, séries, épisodes, musique)",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="scan_library",
            description="Lancer un scan de la bibliothèque Kodi",
            inputSchema={
                "type": "object",
                "properties": {
                    "library_type": {
                        "type": "string",
                        "description": "Type de bibliothèque à scanner",
                        "enum": ["video", "audio"],
                        "default": "video"
                    }
                },
                "required": []
            }
        )
    ]
    
    return ListToolsResult(tools=tools)


@mcp_server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    """Exécute un tool MCP"""
    logger.info(f"Exécution du tool: {name} avec arguments: {arguments}")
    
    try:
        if name == "get_now_playing":
            response = kodi_client.get_now_playing()
            
        elif name == "player_play_pause":
            response = kodi_client.player_play_pause()
            
        elif name == "player_stop":
            response = kodi_client.player_stop()
            
        elif name == "set_volume":
            level = arguments.get("level")
            if level is None:
                response = KodiResponse(success=False, error="Paramètre 'level' manquant")
            else:
                response = kodi_client.set_volume(int(level))
                
        elif name == "navigate_menu":
            direction = arguments.get("direction")
            if direction is None:
                response = KodiResponse(success=False, error="Paramètre 'direction' manquant")
            else:
                response = kodi_client.navigate_menu(str(direction))
                
        elif name == "search_movies":
            query = arguments.get("query")
            if query is None:
                response = KodiResponse(success=False, error="Paramètre 'query' manquant")
            else:
                response = kodi_client.search_movies(str(query))
                
        elif name == "list_recent_movies":
            limit = arguments.get("limit", 20)
            response = kodi_client.list_recent_movies(int(limit))
            
        elif name == "list_tv_shows":
            response = kodi_client.list_tv_shows()
            
        elif name == "play_movie":
            movie_id = arguments.get("movie_id")
            if movie_id is None:
                response = KodiResponse(success=False, error="Paramètre 'movie_id' manquant")
            else:
                response = kodi_client.play_movie(int(movie_id))
                
        elif name == "play_episode":
            tvshow_id = arguments.get("tvshow_id")
            season = arguments.get("season")
            episode = arguments.get("episode")
            
            if any(x is None for x in [tvshow_id, season, episode]):
                response = KodiResponse(success=False, error="Paramètres 'tvshow_id', 'season', 'episode' requis")
            else:
                response = kodi_client.play_episode(int(tvshow_id), int(season), int(episode))
                
        elif name == "get_library_stats":
            response = kodi_client.get_library_stats()
            
        elif name == "scan_library":
            library_type = arguments.get("library_type", "video")
            response = kodi_client.scan_library(str(library_type))
            
        else:
            response = KodiResponse(success=False, error=f"Tool inconnu: {name}")
        
        return kodi_response_to_mcp_result(response, name)
        
    except Exception as e:
        logger.exception(f"Erreur lors de l'exécution du tool {name}")
        error_response = KodiResponse(success=False, error=str(e))
        return kodi_response_to_mcp_result(error_response, name)


# Optionnel: Ajout de prompts prédéfinis
@mcp_server.list_prompts()
async def list_prompts() -> List[Prompt]:
    """Liste les prompts disponibles"""
    return [
        Prompt(
            name="kodi_status",
            description="Vérifier le statut de Kodi et ce qui joue actuellement",
            arguments=[]
        ),
        Prompt(
            name="kodi_control",
            description="Contrôler la lecture sur Kodi (play/pause/stop)",
            arguments=[
                {
                    "name": "action",
                    "description": "Action à effectuer",
                    "required": True
                }
            ]
        )
    ]


@mcp_server.get_prompt()
async def get_prompt(name: str, arguments: Dict[str, str]) -> GetPromptResult:
    """Récupère un prompt prédéfini"""
    if name == "kodi_status":
        return GetPromptResult(
            description="Vérification du statut de Kodi",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text="Peux-tu vérifier ce qui joue actuellement sur Kodi et me donner le statut général ?"
                    )
                )
            ]
        )
    elif name == "kodi_control":
        action = arguments.get("action", "play_pause")
        return GetPromptResult(
            description=f"Contrôle de Kodi: {action}",
            messages=[
                PromptMessage(
                    role="user", 
                    content=TextContent(
                        type="text",
                        text=f"Peux-tu {action} sur Kodi s'il te plaît ?"
                    )
                )
            ]
        )
    else:
        raise ValueError(f"Prompt inconnu: {name}")


async def run_mcp_server():
    """Lance le serveur MCP avec SSE"""
    logger.info("Démarrage du serveur MCP Kodi...")
    logger.info(f"Configuration Kodi: {settings.kodi_host}:{settings.kodi_port}")
    
    # Test de connexion Kodi
    if kodi_client.test_connection():
        logger.info("✅ Connexion Kodi: OK")
    else:
        logger.warning("⚠️  Connexion Kodi: ÉCHEC")
    
    # Création du transport SSE
    transport = SSEServerTransport(
        host=settings.server_host,
        port=settings.server_port
    )
    
    # Options d'initialisation
    init_options = InitializationOptions(
        server_name="kodi-controller",
        server_version="1.0.0"
    )
    
    # Création de la session serveur
    async with ServerSession(transport, mcp_server, init_options) as session:
        logger.info(f"🚀 Serveur MCP démarré sur {settings.server_host}:{settings.server_port}")
        await session.run()


if __name__ == "__main__":
    # Point d'entrée pour le serveur MCP
    asyncio.run(run_mcp_server())