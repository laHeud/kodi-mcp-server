# Dockerfile pour le serveur MCP Kodi
FROM python:3.11-slim

# Métadonnées
LABEL maintainer="Assistant IA" \
      description="Serveur MCP pour contrôler Kodi via HTTP/SSE" \
      version="1.0.0"

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Installation des dépendances système
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Création d'un utilisateur non-root
RUN groupadd -r kodi && useradd -r -g kodi kodi

# Répertoire de travail
WORKDIR /app

# Copie des fichiers de dépendances
COPY requirements.txt .

# Installation des dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source
COPY src/ ./src/

# Création du répertoire de logs
RUN mkdir -p /app/logs && chown -R kodi:kodi /app

# Changement vers l'utilisateur non-root
USER kodi

# Exposition du port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Commande par défaut - Pure MCP Server (standard MCP protocol)
CMD ["python", "-m", "uvicorn", "src.pure_mcp_server:app", "--host", "0.0.0.0", "--port", "8080"]
