"""
Client Kodi pour l'API JSON-RPC
Wrapper avec retry logic et gestion d'erreurs robuste
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

import aiohttp
import requests
from requests.auth import HTTPBasicAuth
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .config import settings


# Configuration du logger
logger = logging.getLogger(__name__)


class KodiError(Exception):
    """Exception de base pour les erreurs Kodi"""
    pass


class KodiConnectionError(KodiError):
    """Erreur de connexion à Kodi"""
    pass


class KodiAPIError(KodiError):
    """Erreur de l'API Kodi"""
    pass


class NavigationDirection(Enum):
    """Directions de navigation dans l'interface Kodi"""
    UP = "up"
    DOWN = "down" 
    LEFT = "left"
    RIGHT = "right"
    SELECT = "select"
    BACK = "back"


@dataclass
class KodiResponse:
    """Réponse formatée de l'API Kodi"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    error_code: Optional[int] = None


class KodiClient:
    """
    Client pour l'API JSON-RPC de Kodi avec retry logic et gestion d'erreurs
    """
    
    def __init__(self):
        self.base_url = settings.kodi_url
        self.auth = None
        self.timeout = settings.kodi_timeout
        self.retry_attempts = settings.kodi_retry_attempts
        self.retry_delay = settings.kodi_retry_delay
        
        # Configuration de l'authentification si nécessaire
        if settings.kodi_auth:
            self.auth = HTTPBasicAuth(*settings.kodi_auth)
        
        logger.info(f"Client Kodi initialisé pour {settings.kodi_host}:{settings.kodi_port}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException, KodiConnectionError))
    )
    def _make_request(self, method: str, params: Optional[Dict] = None) -> KodiResponse:
        """
        Effectue une requête JSON-RPC vers Kodi avec retry automatique
        
        Args:
            method: Méthode JSON-RPC à appeler
            params: Paramètres de la méthode
        
        Returns:
            KodiResponse avec le résultat
        """
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": 1
        }
        
        if params:
            payload["params"] = params
        
        try:
            logger.debug(f"Requête Kodi: {method} avec params: {params}")
            
            response = requests.post(
                self.base_url,
                json=payload,
                auth=self.auth,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                error_msg = f"Erreur HTTP {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise KodiConnectionError(error_msg)
            
            response_data = response.json()
            
            # Vérifier les erreurs JSON-RPC
            if "error" in response_data:
                error = response_data["error"]
                error_msg = f"Erreur API Kodi: {error.get('message', 'Erreur inconnue')}"
                logger.error(error_msg)
                return KodiResponse(
                    success=False,
                    error=error.get('message'),
                    error_code=error.get('code')
                )
            
            # Succès
            result = response_data.get("result")
            logger.debug(f"Réponse Kodi réussie pour {method}: {result}")
            
            return KodiResponse(success=True, data=result)
        
        except requests.exceptions.Timeout:
            error_msg = f"Timeout lors de la requête {method} (>{self.timeout}s)"
            logger.error(error_msg)
            raise KodiConnectionError(error_msg)
        
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Impossible de se connecter à Kodi: {str(e)}"
            logger.error(error_msg)
            raise KodiConnectionError(error_msg)
        
        except json.JSONDecodeError as e:
            error_msg = f"Réponse JSON invalide de Kodi: {str(e)}"
            logger.error(error_msg)
            raise KodiAPIError(error_msg)
        
        except Exception as e:
            error_msg = f"Erreur inattendue lors de la requête {method}: {str(e)}"
            logger.error(error_msg)
            raise KodiAPIError(error_msg)
    
    def ping(self) -> KodiResponse:
        """Test de connexion à Kodi"""
        return self._make_request("JSONRPC.Ping")
    
    def get_now_playing(self) -> KodiResponse:
        """Récupère les informations du média en cours de lecture"""
        response = self._make_request("Player.GetActivePlayers")
        
        if not response.success or not response.data:
            return KodiResponse(success=True, data={"status": "nothing_playing"})
        
        # Récupérer les détails du player actif
        player_id = response.data[0]["playerid"]
        
        # Propriétés de base compatibles avec tous les types de média
        basic_properties = [
            "title", "duration", "file", "thumbnail"
        ]
        
        # Essayer d'abord avec les propriétés de base
        item_response = self._make_request(
            "Player.GetItem",
            {
                "playerid": player_id,
                "properties": basic_properties
            }
        )
        
        if not item_response.success:
            logger.warning(f"Échec Player.GetItem avec propriétés de base: {item_response.error}")
            # Essayer sans propriétés
            item_response = self._make_request(
                "Player.GetItem",
                {"playerid": player_id}
            )
        
        # Récupérer les propriétés du player (plus fiable)
        player_props = ["time", "totaltime", "percentage", "speed"]
        props_response = self._make_request(
            "Player.GetProperties",
            {
                "playerid": player_id,
                "properties": player_props
            }
        )
        
        if not props_response.success:
            logger.warning(f"Échec Player.GetProperties: {props_response.error}")
            # Essayer avec moins de propriétés
            props_response = self._make_request(
                "Player.GetProperties",
                {
                    "playerid": player_id,
                    "properties": ["time", "totaltime"]
                }
            )
        
        # Combiner les données disponibles
        result = {
            "status": "playing",
            "player_id": player_id,
            "player_type": response.data[0].get("type", "unknown")
        }
        
        if item_response.success and item_response.data:
            result["item"] = item_response.data.get("item", {})
        
        if props_response.success and props_response.data:
            result["properties"] = props_response.data
        
        return KodiResponse(success=True, data=result)
    
    def player_play_pause(self) -> KodiResponse:
        """Toggle play/pause du player actif"""
        # Récupérer le player actif
        response = self._make_request("Player.GetActivePlayers")
        
        if not response.success or not response.data:
            return KodiResponse(success=False, error="Aucun player actif")
        
        player_id = response.data[0]["playerid"]
        
        return self._make_request("Player.PlayPause", {"playerid": player_id})
    
    def player_stop(self) -> KodiResponse:
        """Arrêter la lecture"""
        response = self._make_request("Player.GetActivePlayers")
        
        if not response.success or not response.data:
            return KodiResponse(success=False, error="Aucun player actif")
        
        player_id = response.data[0]["playerid"]
        
        return self._make_request("Player.Stop", {"playerid": player_id})
    
    def set_volume(self, level: int) -> KodiResponse:
        """
        Régler le volume
        
        Args:
            level: Niveau de volume (0-100)
        """
        if not 0 <= level <= 100:
            return KodiResponse(success=False, error="Le volume doit être entre 0 et 100")
        
        return self._make_request("Application.SetVolume", {"volume": level})
    
    def navigate_menu(self, direction: str) -> KodiResponse:
        """
        Navigation dans l'interface Kodi
        
        Args:
            direction: Direction (up/down/left/right/select/back)
        """
        try:
            nav_direction = NavigationDirection(direction.lower())
        except ValueError:
            valid_directions = [d.value for d in NavigationDirection]
            return KodiResponse(
                success=False, 
                error=f"Direction invalide. Doit être un de: {valid_directions}"
            )
        
        # Mapping des directions vers les méthodes Kodi
        direction_mapping = {
            NavigationDirection.UP: "Input.Up",
            NavigationDirection.DOWN: "Input.Down",
            NavigationDirection.LEFT: "Input.Left",
            NavigationDirection.RIGHT: "Input.Right",
            NavigationDirection.SELECT: "Input.Select",
            NavigationDirection.BACK: "Input.Back"
        }
        
        method = direction_mapping[nav_direction]
        return self._make_request(method)
    
    def search_movies(self, query: str) -> KodiResponse:
        """
        Chercher des films dans la bibliothèque
        
        Args:
            query: Terme de recherche
        """
        if not query.strip():
            return KodiResponse(success=False, error="La requête de recherche ne peut pas être vide")
        
        properties = [
            "title", "year", "rating", "runtime", "plot", "director", 
            "genre", "thumbnail", "fanart", "file"
        ]
        
        return self._make_request(
            "VideoLibrary.GetMovies",
            {
                "filter": {
                    "operator": "contains",
                    "field": "title",
                    "value": query
                },
                "properties": properties,
                "sort": {"order": "ascending", "method": "title"}
            }
        )
    
    def list_recent_movies(self, limit: int = 20) -> KodiResponse:
        """
        Liste les films récemment ajoutés
        
        Args:
            limit: Nombre de films à retourner (défaut: 20)
        """
        properties = [
            "title", "year", "rating", "runtime", "plot", "director",
            "genre", "thumbnail", "fanart", "dateadded", "file"
        ]
        
        return self._make_request(
            "VideoLibrary.GetRecentlyAddedMovies",
            {
                "properties": properties,
                "limits": {"end": limit}
            }
        )
    
    def list_tv_shows(self) -> KodiResponse:
        """Liste toutes les séries TV"""
        properties = [
            "title", "year", "rating", "plot", "genre", "thumbnail", 
            "fanart", "premiered", "studio", "mpaa", "file"
        ]
        
        return self._make_request(
            "VideoLibrary.GetTVShows",
            {
                "properties": properties,
                "sort": {"order": "ascending", "method": "title"}
            }
        )
    
    def play_movie(self, movie_id: int) -> KodiResponse:
        """
        Lancer un film
        
        Args:
            movie_id: ID du film dans la bibliothèque Kodi
        """
        return self._make_request(
            "Player.Open",
            {
                "item": {
                    "movieid": movie_id
                }
            }
        )
    
    def play_episode(self, tvshow_id: int, season: int, episode: int) -> KodiResponse:
        """
        Lancer un épisode de série
        
        Args:
            tvshow_id: ID de la série
            season: Numéro de saison
            episode: Numéro d'épisode
        """
        # D'abord, récupérer l'ID de l'épisode
        episodes_response = self._make_request(
            "VideoLibrary.GetEpisodes",
            {
                "tvshowid": tvshow_id,
                "season": season,
                "properties": ["episode"]
            }
        )
        
        if not episodes_response.success or not episodes_response.data:
            return KodiResponse(success=False, error="Épisode introuvable")
        
        # Trouver l'épisode correspondant
        target_episode = None
        for ep in episodes_response.data.get("episodes", []):
            if ep.get("episode") == episode:
                target_episode = ep
                break
        
        if not target_episode:
            return KodiResponse(success=False, error=f"Épisode {season}x{episode:02d} introuvable")
        
        return self._make_request(
            "Player.Open",
            {
                "item": {
                    "episodeid": target_episode["episodeid"]
                }
            }
        )
    
    def get_library_stats(self) -> KodiResponse:
        """Récupérer les statistiques de la bibliothèque"""
        try:
            # Récupérer les stats des films
            movies_response = self._make_request("VideoLibrary.GetMovies", {"limits": {"end": 0}})
            movies_count = 0
            if movies_response.success and movies_response.data:
                movies_count = movies_response.data.get("limits", {}).get("total", 0)
            
            # Récupérer les stats des séries
            shows_response = self._make_request("VideoLibrary.GetTVShows", {"limits": {"end": 0}})
            shows_count = 0
            if shows_response.success and shows_response.data:
                shows_count = shows_response.data.get("limits", {}).get("total", 0)
            
            # Récupérer les stats des épisodes
            episodes_response = self._make_request("VideoLibrary.GetEpisodes", {"limits": {"end": 0}})
            episodes_count = 0
            if episodes_response.success and episodes_response.data:
                episodes_count = episodes_response.data.get("limits", {}).get("total", 0)
            
            # Récupérer les stats musicales
            songs_response = self._make_request("AudioLibrary.GetSongs", {"limits": {"end": 0}})
            songs_count = 0
            if songs_response.success and songs_response.data:
                songs_count = songs_response.data.get("limits", {}).get("total", 0)
            
            stats = {
                "movies": movies_count,
                "tv_shows": shows_count,
                "episodes": episodes_count,
                "songs": songs_count,
                "total_video_items": movies_count + episodes_count
            }
            
            return KodiResponse(success=True, data=stats)
        
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques: {e}")
            return KodiResponse(success=False, error=str(e))
    
    def scan_library(self, library_type: str = "video") -> KodiResponse:
        """
        Lancer un scan de la bibliothèque
        
        Args:
            library_type: Type de bibliothèque ("video" ou "audio")
        """
        if library_type.lower() == "video":
            return self._make_request("VideoLibrary.Scan")
        elif library_type.lower() == "audio":
            return self._make_request("AudioLibrary.Scan")
        else:
            return KodiResponse(
                success=False,
                error="Type de bibliothèque invalide. Doit être 'video' ou 'audio'"
            )
    
    def get_volume(self) -> KodiResponse:
        """Récupérer le niveau de volume actuel"""
        return self._make_request("Application.GetProperties", {"properties": ["volume", "muted"]})
    
    def format_file_size(self, size_bytes: int) -> str:
        """
        Formate une taille en octets en format lisible (GB/MB/KB)
        
        Args:
            size_bytes: Taille en octets
        
        Returns:
            Chaîne formatée (ex: "1.5 GB", "245 MB")
        """
        if size_bytes == 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                if unit == 'B':
                    return f"{size_bytes} {unit}"
                else:
                    return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"
    
    def list_directory(self, path: str, limit: int = 50) -> KodiResponse:
        """
        Liste les fichiers vidéo dans un répertoire via l'API Kodi Files.GetDirectory
        
        Args:
            path: Chemin du répertoire à lister
            limit: Nombre maximum de fichiers à retourner
        
        Returns:
            KodiResponse avec la liste des fichiers vidéo
        """
        try:
            # Paramètres pour Files.GetDirectory selon la doc Kodi
            params = {
                "directory": path
            }
            
            response = self._make_request("Files.GetDirectory", params)
            
            if not response.success:
                return KodiResponse(
                    success=False,
                    error=f"Impossible d'accéder au dossier: {response.error}",
                    error_code="DIRECTORY_ACCESS_ERROR"
                )
            
            files = []
            total_processed = 0
            
            if response.data and "files" in response.data:
                video_extensions = [".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".flv", ".webm"]
                
                for file_info in response.data["files"]:
                    if total_processed >= limit:
                        break
                        
                    # Ne traiter que les fichiers (pas les dossiers pour l'instant)
                    if file_info.get("filetype") == "file":
                        file_path = file_info.get("file", "")
                        
                        # Vérifier si c'est un fichier vidéo
                        if any(file_path.lower().endswith(ext) for ext in video_extensions):
                            file_size = file_info.get("size", 0)
                            files.append({
                                "name": file_path.split("/")[-1],  # Nom du fichier
                                "path": file_path,
                                "size": file_size,
                                "size_formatted": self.format_file_size(file_size),
                                "modified": file_info.get("datemodified", ""),
                                "type": "video"
                            })
                            total_processed += 1
            
            return KodiResponse(
                success=True,
                data={
                    "files": files,
                    "total": len(files),
                    "path": path,
                    "limit": limit
                }
            )
            
        except Exception as e:
            logger.error(f"Erreur lors du listing du répertoire {path}: {e}")
            return KodiResponse(
                success=False,
                error=f"Erreur lors du listing: {str(e)}",
                error_code="DIRECTORY_LIST_ERROR"
            )
    
    def play_file(self, file_path: str) -> KodiResponse:
        """
        Lance la lecture d'un fichier par son chemin via Player.Open
        
        Args:
            file_path: Chemin complet du fichier à lire
        
        Returns:
            KodiResponse avec le résultat de l'opération
        """
        if not file_path or not file_path.strip():
            return KodiResponse(success=False, error="Le chemin du fichier ne peut pas être vide")
        
        try:
            params = {
                "item": {
                    "file": file_path.strip()
                }
            }
            
            response = self._make_request("Player.Open", params)
            
            if response.success:
                return KodiResponse(
                    success=True,
                    data={
                        "message": f"Lecture lancée: {file_path.split('/')[-1]}",
                        "file_path": file_path,
                        "status": "playing"
                    }
                )
            else:
                return KodiResponse(
                    success=False,
                    error=f"Impossible de lancer le fichier: {response.error}",
                    error_code="FILE_PLAY_ERROR"
                )
                
        except Exception as e:
            logger.error(f"Erreur lors de la lecture du fichier {file_path}: {e}")
            return KodiResponse(
                success=False,
                error=f"Erreur lors de la lecture: {str(e)}",
                error_code="FILE_PLAY_EXCEPTION"
            )
    
    def search_in_directory(self, path: str, query: str) -> KodiResponse:
        """
        Cherche des fichiers vidéo dans un répertoire par nom (insensible à la casse)
        
        Args:
            path: Chemin du répertoire à chercher
            query: Terme de recherche
        
        Returns:
            KodiResponse avec les fichiers trouvés
        """
        if not query or not query.strip():
            return KodiResponse(success=False, error="Le terme de recherche ne peut pas être vide")
        
        try:
            # D'abord lister tous les fichiers du répertoire
            list_response = self.list_directory(path, limit=100)  # Plus de fichiers pour la recherche
            
            if not list_response.success:
                return KodiResponse(
                    success=False,
                    error=f"Impossible de lister le répertoire: {list_response.error}",
                    error_code="SEARCH_DIRECTORY_ERROR"
                )
            
            # Filtrer par le terme de recherche (insensible à la casse)
            query_lower = query.strip().lower()
            filtered_files = []
            
            files_data = list_response.data.get("files", [])
            for file_info in files_data:
                file_name = file_info.get("name", "")
                file_path = file_info.get("path", "")
                
                # Rechercher dans le nom du fichier ET dans le chemin
                if (query_lower in file_name.lower() or 
                    query_lower in file_path.lower()):
                    filtered_files.append(file_info)
            
            return KodiResponse(
                success=True,
                data={
                    "files": filtered_files,
                    "total": len(filtered_files),
                    "query": query,
                    "path": path
                }
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche dans {path} avec '{query}': {e}")
            return KodiResponse(
                success=False,
                error=f"Erreur lors de la recherche: {str(e)}",
                error_code="SEARCH_EXCEPTION"
            )
    
    def calculate_match_score(self, filename: str, query: str) -> float:
        """
        Calcule un score de pertinence pour un fichier par rapport à une requête
        
        Args:
            filename: Nom du fichier
            query: Terme de recherche
        
        Returns:
            Score de pertinence (plus élevé = plus pertinent)
        """
        filename_lower = filename.lower()
        query_lower = query.lower().strip()
        
        if not query_lower:
            return 0.0
        
        score = 0.0
        
        # Score de base si le terme est trouvé
        if query_lower in filename_lower:
            score += 10.0
        
        # Bonus si c'est au début du nom
        if filename_lower.startswith(query_lower):
            score += 20.0
        
        # Bonus pour correspondance de mots complets
        query_words = query_lower.split()
        filename_words = filename_lower.replace(".", " ").replace("_", " ").replace("-", " ").split()
        
        for query_word in query_words:
            if query_word in filename_words:
                score += 15.0
            # Bonus pour correspondance partielle de mot
            for filename_word in filename_words:
                if query_word in filename_word:
                    score += 5.0
        
        # Malus pour fichiers très longs (sample, trailer, etc.)
        suspicious_keywords = ["sample", "trailer", "preview", "demo"]
        for keyword in suspicious_keywords:
            if keyword in filename_lower:
                score -= 10.0
        
        # Bonus pour qualité (1080p, 720p, etc.)
        quality_keywords = ["1080p", "720p", "4k", "hd", "bluray", "webrip"]
        for keyword in quality_keywords:
            if keyword in filename_lower:
                score += 2.0
        
        return score
    
    def find_best_match_and_play(self, path: str, query: str, auto_play: bool = True) -> KodiResponse:
        """
        Recherche intelligente et lecture automatique du meilleur fichier trouvé
        
        Args:
            path: Chemin du répertoire à chercher
            query: Terme de recherche (peut être partiel)
            auto_play: Si True, lance automatiquement le meilleur résultat
        
        Returns:
            KodiResponse avec les résultats et l'action effectuée
        """
        if not query or not query.strip():
            return KodiResponse(success=False, error="Le terme de recherche ne peut pas être vide")
        
        try:
            # Rechercher tous les fichiers correspondants
            search_response = self.search_in_directory(path, query)
            
            if not search_response.success:
                return KodiResponse(
                    success=False,
                    error=f"Erreur de recherche: {search_response.error}",
                    error_code="SMART_SEARCH_ERROR"
                )
            
            files = search_response.data.get("files", [])
            
            if not files:
                return KodiResponse(
                    success=False,
                    error=f"Aucun fichier trouvé pour '{query}' dans {path}",
                    error_code="NO_MATCH_FOUND"
                )
            
            # Calculer le score de pertinence pour chaque fichier
            scored_files = []
            for file_info in files:
                filename = file_info.get("name", "")
                score = self.calculate_match_score(filename, query)
                scored_files.append({
                    **file_info,
                    "relevance_score": score
                })
            
            # Trier par score décroissant
            scored_files.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            
            best_match = scored_files[0] if scored_files else None
            
            if not best_match:
                return KodiResponse(
                    success=False,
                    error="Aucun fichier valide trouvé",
                    error_code="NO_VALID_MATCH"
                )
            
            result_data = {
                "query": query,
                "total_found": len(files),
                "best_match": best_match,
                "all_matches": scored_files[:5],  # Top 5 pour information
                "path": path,
                "auto_played": False
            }
            
            # Lancer automatiquement si demandé
            if auto_play:
                file_path = best_match.get("path")
                if file_path:
                    play_response = self.play_file(file_path)
                    
                    if play_response.success:
                        result_data["auto_played"] = True
                        result_data["play_status"] = "success"
                        result_data["message"] = f"Lecture lancée: {best_match.get('name')}"
                    else:
                        result_data["play_status"] = "failed"
                        result_data["play_error"] = play_response.error
            
            return KodiResponse(
                success=True,
                data=result_data
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche intelligente pour '{query}': {e}")
            return KodiResponse(
                success=False,
                error=f"Erreur lors de la recherche intelligente: {str(e)}",
                error_code="SMART_SEARCH_EXCEPTION"
            )
    
    def test_connection(self) -> bool:
        """
        Test simple de connexion à Kodi
        
        Returns:
            True si la connexion fonctionne, False sinon
        """
        try:
            response = self.ping()
            return response.success and response.data == "pong"
        except Exception as e:
            logger.error(f"Test de connexion échoué: {e}")
            return False
    
    def test_connection(self) -> bool:
        """
        Test simple de connexion à Kodi
        
        Returns:
            True si la connexion fonctionne, False sinon
        """
        try:
            response = self.ping()
            return response.success and response.data == "pong"
        except Exception as e:
            logger.error(f"Test de connexion échoué: {e}")
            return False
