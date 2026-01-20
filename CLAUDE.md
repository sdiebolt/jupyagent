# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

JupyAgent is a Python CLI tool that creates a secure, sandboxed LLM Agent environment using Docker. It orchestrates Jupyter Lab, Jupyter MCP Server, Opencode Agent, and Zellij web terminal in a containerized setup.

## Commands

**Run the tool:**
```bash
# One-shot execution (no install)
uvx --from git+https://github.com/sdiebolt/jupyagent jupyagent

# Or after installation
jupyagent
```

**Install for development:**
```bash
uv pip install -e .
```

There are no tests, linting, or type-checking configured.

## Architecture

The entire application lives in `src/jupyagent/main.py` (~645 lines). It follows this flow:

1. **Entry point** (`run()`) - Checks Docker prerequisites, detects if `sudo docker` is needed on Linux
2. **Configuration** - Stored in `~/.jupyagent/` (config.json, .env, docker-compose.yml)
3. **Setup** (`cmd_setup()`) - Prompts for paths, generates Dockerfile and docker-compose.yml dynamically, builds the image
4. **Dashboard** (`cmd_dashboard()`) - Interactive TUI loop using questionary for service management

**Key generated files (at runtime):**
- `~/.jupyagent/jupyter/Dockerfile` - Multi-service container with Jupyter, Zellij, Opencode, and MCP server
- `~/.jupyagent/docker-compose.yml` - Service definition with volume mounts
- `~/.jupyagent/.env` - Environment variables for compose

**Port mappings:**
- 8888: Jupyter Lab
- 8282: Zellij web terminal
- 3000: Opencode web UI

**Volume strategy:**
- Read-only mount at `/mnt/ro_data` for context
- Read-write mount at `/workspace` for agent output
- Opencode config/data persisted to `~/.jupyagent/opencode_config/` and `~/.jupyagent/opencode_data/`

## Key Patterns

- All Docker commands go through the global `DOCKER_CMD` list (either `["docker"]` or `["sudo", "docker"]`)
- Configuration uses JSON (`config.json`) for persistent settings
- Zellij token is written to `/workspace/ZELLIJ_TOKEN.txt` at container startup and read by the dashboard
- The Dockerfile and compose files are generated as Python strings with variable substitution
