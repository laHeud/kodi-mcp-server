"""
Configuration du serveur MCP Kodi
Gère toutes les variables d'environnement avec validation
"""

from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings
from pathlib import Path
import os


class Settings(BaseSettings):
    """Configuration principale du serveur MCP Kodi"""
    
    # Configuration Kodi
    kodi_host: str = Field(default="192.168.1.100", description="Adresse IP de Kodi")
    kodi_port: int = Field(default=8080, description="Port JSON-RPC de Kodi")
    kodi_username: str = Field(default="kodi", description="Nom d'utilisateur Kodi")
    kodi_password: str = Field(default="", description="Mot de passe Kodi")
    
    # Configuration du serveur MCP
    server_host: str = Field(default="0.0.0.0", description="Adresse d'écoute du serveur")
    server_port: int = Field(default=8080, description="Port d'écoute du serveur")
    mcp_server_name: str = Field(default="kodi-controller", description="Nom du serveur MCP")
    
    # Configuration des timeouts et retry
    kodi_timeout: int = Field(default=5, description="Timeout des requêtes Kodi en secondes")
    kodi_retry_attempts: int = Field(default=3, description="Nombre de tentatives de retry")
    kodi_retry_delay: int = Field(default=1, description="Délai entre les tentatives en secondes")
    
    # Configuration des logs
    log_level: str = Field(default="INFO", description="Niveau de logging")
    log_format: str = Field(default="json", description="Format de logging (json/text)")
    
    # Configuration de sécurité
    api_key: Optional[str] = Field(default=None, description="Clé API optionnelle")
    allowed_origins: str = Field(default="*", description="Origines CORS autorisées")
    
    # Configuration du dossier downloads
    kodi_downloads_path: str = Field(default="/media/Stockage/Download/completed/", description="Chemin du dossier downloads Kodi")
    
    # Configuration pour production
    environment: str = Field(default="development", description="Environnement (development/production)")
    
    @validator('kodi_port', 'server_port')
    def validate_port(cls, v):
        """Valide que les ports sont dans la plage valide"""
        if not 1 <= v <= 65535:
            raise ValueError(f"Le port doit être entre 1 et 65535, reçu: {v}")
        return v
    
    @validator('log_level')
    def validate_log_level(cls, v):
        """Valide le niveau de logging"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Niveau de log invalide. Doit être un de: {valid_levels}")
        return v.upper()
    
    @validator('log_format')
    def validate_log_format(cls, v):
        """Valide le format de logging"""
        valid_formats = ['json', 'text']
        if v.lower() not in valid_formats:
            raise ValueError(f"Format de log invalide. Doit être un de: {valid_formats}")
        return v.lower()
    
    @validator('kodi_timeout', 'kodi_retry_attempts', 'kodi_retry_delay')
    def validate_positive_int(cls, v):
        """Valide que les valeurs entières sont positives"""
        if v <= 0:
            raise ValueError(f"La valeur doit être positive, reçu: {v}")
        return v
    
    @validator('allowed_origins')
    def validate_allowed_origins(cls, v):
        """Valide les origines CORS"""
        if not v or v.strip() == "":
            return "*"
        return v
    
    @property
    def kodi_url(self) -> str:
        """URL complète pour l'API JSON-RPC de Kodi"""
        return f"http://{self.kodi_host}:{self.kodi_port}/jsonrpc"
    
    @property
    def kodi_auth(self) -> Optional[tuple]:
        """Tuple d'authentification pour Kodi si nécessaire"""
        if self.kodi_username and self.kodi_password:
            return (self.kodi_username, self.kodi_password)
        return None
    
    @property
    def is_production(self) -> bool:
        """Indique si on est en environnement de production"""
        return self.environment.lower() == "production"
    
    @property
    def cors_origins(self) -> List[str]:
        """Liste des origines CORS formatée"""
        if self.allowed_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]
    
    class Config:
        """Configuration de pydantic"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Instance globale des settings
settings = Settings()


def get_settings() -> Settings:
    """
    Récupère l'instance des settings
    Utile pour les dépendances FastAPI
    """
    return settings


def load_env_file(env_path: Optional[str] = None) -> None:
    """
    Charge un fichier .env spécifique
    """
    from dotenv import load_dotenv
    
    # En environnement Docker, les variables sont injectées via docker-compose
    # On essaie quand même de charger le .env pour le développement local
    if env_path:
        env_file = Path(env_path)
        if env_file.exists():
            load_dotenv(env_file)
            print(f"✅ Fichier .env chargé: {env_file}")
    else:
        # Cherche .env dans plusieurs emplacements
        possible_paths = [
            Path.cwd() / ".env",
            Path("/app") / ".env",
            Path.cwd().parent / ".env"
        ]
        
        for env_file in possible_paths:
            if env_file.exists():
                load_dotenv(env_file)
                print(f"✅ Fichier .env chargé: {env_file}")
                return
        
        print("⚠️  Aucun fichier .env trouvé, utilisation des variables d'environnement")


def validate_kodi_connection() -> bool:
    """
    Valide la configuration de connexion Kodi
    """
    import requests
    from requests.auth import HTTPBasicAuth
    
    try:
        url = settings.kodi_url
        auth = None
        if settings.kodi_auth:
            auth = HTTPBasicAuth(*settings.kodi_auth)
        
        # Test de connexion simple
        payload = {
            "jsonrpc": "2.0",
            "method": "JSONRPC.Ping",
            "id": 1
        }
        
        response = requests.post(
            url,
            json=payload,
            auth=auth,
            timeout=settings.kodi_timeout
        )
        
        return response.status_code == 200 and response.json().get("result") == "pong"
    
    except Exception as e:
        print(f"❌ Erreur de connexion Kodi: {e}")
        return False


# Chargement automatique du .env au moment de l'import
load_env_file()