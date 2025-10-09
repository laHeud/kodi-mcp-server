# Kodi MCP Server

A Model Context Protocol (MCP) server for controlling Kodi media center. This server provides both REST API and MCP protocol support, allowing seamless integration with MCP clients like Claude Desktop, n8n, and other MCP-compatible tools.

## Features

### Core Kodi Controls
- 🎮 **Player Control**: Play, pause, stop, volume control
- 🧭 **Navigation**: Menu navigation (up, down, left, right, select, back)
- 📊 **Library Management**: View library statistics, scan library
- 🎬 **Movie Operations**: Search movies, list recent movies, play by ID
- 📺 **TV Show Operations**: List TV shows, play episodes

### Smart Downloads Management
- 📁 **List Downloads**: Browse video files in download directory
- 🔍 **Search Downloads**: Find files by name (case-insensitive)
- 🎯 **Smart Find & Play**: Intelligent search with automatic playback of best match
- 📂 **Direct File Play**: Play any video file by path

### Protocol Support
- 🌐 **REST API**: Direct HTTP endpoints for easy integration
- 🔌 **MCP Protocol**: Full Model Context Protocol support
- 📡 **Server-Sent Events**: Real-time event streaming
- 🔗 **WebSocket**: Bidirectional communication support

## Quick Start

### Using Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/kodi-mcp-server.git
   cd kodi-mcp-server
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your Kodi configuration
   ```

3. **Start with Docker Compose**
   ```bash
   docker-compose up -d
   ```

4. **Verify installation**
   ```bash
   curl http://localhost:8080/health
   ```

### Manual Installation

1. **Requirements**
   - Python 3.11+
   - Kodi with JSON-RPC enabled
   - Network access to Kodi instance

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   export KODI_HOST=192.168.1.100
   export KODI_PORT=8080
   export KODI_USERNAME=kodi
   export KODI_PASSWORD=your_password
   export KODI_DOWNLOADS_PATH=/path/to/downloads
   ```

4. **Run the server**
   ```bash
   python -m src.server
   ```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `KODI_HOST` | Kodi server IP address | `localhost` | Yes |
| `KODI_PORT` | Kodi JSON-RPC port | `8080` | Yes |
| `KODI_USERNAME` | Kodi username | - | Yes |
| `KODI_PASSWORD` | Kodi password | - | Yes |
| `KODI_DOWNLOADS_PATH` | Path to downloads folder | - | Yes |
| `SERVER_HOST` | MCP server bind address | `0.0.0.0` | No |
| `SERVER_PORT` | MCP server port | `8080` | No |
| `MCP_SERVER_NAME` | MCP server identifier | `kodi-controller` | No |
| `LOG_LEVEL` | Logging level | `INFO` | No |

### Kodi Setup

1. **Enable JSON-RPC in Kodi**
   - Settings → Services → Control
   - Enable "Allow remote control via HTTP"
   - Set username and password
   - Note the port (usually 8080)

2. **Configure Downloads Path**
   - Use the actual path as seen by Kodi
   - For Docker Kodi: usually `/storage/downloads/` or `/var/media/`
   - Test with `Files.GetDirectory` in Kodi JSON-RPC

## Available Tools

### Player Control
- `get_now_playing` - Get currently playing media information
- `player_play_pause` - Toggle play/pause
- `player_stop` - Stop playbook
- `set_volume` - Set volume level (0-100)

### Navigation
- `navigate_menu` - Navigate Kodi interface (up/down/left/right/select/back)

### Library Operations
- `search_movies` - Search movies in Kodi library
- `list_recent_movies` - List recently added movies
- `list_tv_shows` - List all TV shows
- `play_movie` - Play movie by library ID
- `play_episode` - Play TV show episode
- `get_library_stats` - Get library statistics
- `scan_library` - Trigger library scan

### Downloads Management
- `list_downloads` - List video files in downloads directory
- `search_downloads` - Search downloads by filename
- `play_file` - Play video file by path
- `find_and_play` - Smart search with automatic best-match playback

## Usage Examples

### With MCP Client (Claude Desktop, n8n)

```json
{
  "tool": "find_and_play",
  "arguments": {
    "query": "avengers",
    "auto_play": true
  }
}
```

### REST API

```bash
# Search and play the best matching file
curl -X POST http://localhost:8080/tools/find_and_play \
  -H "Content-Type: application/json" \
  -d '{"params": {"query": "batman", "auto_play": true}}'

# List recent movies
curl -X POST http://localhost:8080/tools/list_recent_movies \
  -H "Content-Type: application/json" \
  -d '{"params": {"limit": 10}}'

# Control playback
curl -X POST http://localhost:8080/tools/player_play_pause \
  -H "Content-Type: application/json" \
  -d '{}'
```

### MCP JSON-RPC Protocol

```bash
# Initialize connection
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "initialize", "id": 1}'

# List available tools
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 2}'

# Execute tool
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", 
    "method": "tools/call", 
    "params": {
      "name": "find_and_play",
      "arguments": {"query": "matrix", "auto_play": true}
    },
    "id": 3
  }'
```

## Integration

### n8n MCP Client

1. Add MCP Client node in n8n
2. Configure connection:
   - **Transport**: Server-Sent Events
   - **URL**: `http://your-server:8080`
3. Use available tools in your workflows

### Claude Desktop

Add to your Claude Desktop MCP configuration:

```json
{
  "mcpServers": {
    "kodi-controller": {
      "command": "docker",
      "args": ["exec", "kodi-mcp-server", "python", "-m", "src.pure_mcp_server"],
      "env": {}
    }
  }
}
```

## Smart Search Algorithm

The `find_and_play` tool uses an intelligent scoring algorithm:

- **🎯 Position Matching**: Terms at the beginning get higher scores
- **🔤 Word Matching**: Complete word matches vs partial matches
- **⭐ Quality Bonus**: Higher quality formats (1080p, BluRay) get bonus points
- **⚠️ Suspicious File Detection**: Samples, trailers get penalty points
- **🧠 Fuzzy Matching**: Works with partial terms like "batman" → "The Dark Knight"

## API Reference

### Health Check
```
GET /health
```

### List Tools
```
GET /tools
```

### Execute Tool (REST)
```
POST /tools/{tool_name}
Content-Type: application/json

{
  "params": {
    "param1": "value1",
    "param2": "value2"
  }
}
```

### MCP Protocol Endpoints
```
POST /          # JSON-RPC MCP protocol
GET /           # Server-Sent Events stream
GET /sse        # Additional SSE endpoint
```

## Development

### Running Tests

```bash
# Test new tools functionality
./demo_smart_search.sh

# Test all tools
./demo_new_tools_working.sh

# Quick Docker test
./quick_docker_test.sh
```

### Project Structure

```
kodi-mcp-server/
├── src/
│   ├── __init__.py
│   ├── config.py           # Configuration management
│   ├── kodi_client.py      # Kodi JSON-RPC client
│   ├── server.py          # Main server entry point
│   ├── hybrid_server.py   # Hybrid REST+MCP server
│   └── pure_mcp_server.py # Pure MCP protocol server
├── docker-compose.yml     # Docker deployment
├── Dockerfile            # Container definition
├── requirements.txt      # Python dependencies
├── .env.example         # Environment template
└── README.md           # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- 🐛 **Issues**: [GitHub Issues](https://github.com/your-username/kodi-mcp-server/issues)
- 📖 **Documentation**: [MCP Protocol Specification](https://github.com/modelcontextprotocol/specification)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/your-username/kodi-mcp-server/discussions)

## Acknowledgments

- [Model Context Protocol](https://modelcontextprotocol.io/) - The protocol specification
- [Kodi](https://kodi.tv/) - The amazing media center software
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework for the hybrid server