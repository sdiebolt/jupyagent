# JupyAgent

**JupyAgent** is a unified installer and manager for a sandboxed LLM Agent environment. It sets up a secure workspace with a Jupyter Server, a Jupyter MCP Server, and an LLM Agent (like Opencode or Claude Code).

## Features
- **One-Command Install:** Easy setup on Windows, Linux, and macOS.
- **Sandboxed Security:** Agents are restricted to a specific workspace directory (`rw`) and can only read other drives (`ro`).
- **Integrated Stack:** Jupyter Lab + Jupyter MCP + LLM Agent pre-wired.
- **Cross-Platform:** Works seamlessly on Windows and Linux via Docker.

## Installation

### Linux / macOS
```bash
curl -Ls https://raw.githubusercontent.com/sdiebolt/jupyagent/main/install.sh | bash
```

### Windows (PowerShell)
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/sdiebolt/jupyagent/main/install.ps1 | iex"
```

## Usage

Once installed, use the `jupyagent` command:

1. **Setup:**
   On first run, it will ask for your configuration (API keys, paths).
   ```bash
   jupyagent
   ```

2. **Start:**
   Launches the environment.
   ```bash
   jupyagent start
   ```

3. **Stop:**
   Stops all containers.
   ```bash
   jupyagent stop
   ```

## Configuration

Configuration is stored in `~/.jupyagent/config.json`. You can re-run the setup wizard at any time:
```bash
jupyagent setup
```
