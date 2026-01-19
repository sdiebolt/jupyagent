# JupyAgent

**JupyAgent** is a unified manager for a sandboxed LLM Agent environment. It sets up a secure workspace with a Jupyter Server, a Jupyter MCP Server, and the **Opencode** Agent.

## Features
- **Secure Sandbox:** Agents are restricted to a specific workspace directory (`rw`) and can only read other drives (`ro`).
- **Integrated Stack:** Jupyter Lab + Jupyter MCP + LLM Agent pre-wired.
- **Cross-Platform:** Works seamlessly on Windows and Linux via Docker.
- **TUI Dashboard:** Modern terminal interface to manage services.

## Prerequisites
1. **Docker:** Must be installed and running.
2. **uv:** The Python package manager. [Install uv](https://docs.astral.sh/uv/getting-started/installation/)

## Installation

You can run JupyAgent directly without installing it using `uvx`:

```bash
# Export your API Key first (Required for the Agent)
export ANTHROPIC_API_KEY="sk-..."

# Run from GitHub
uvx --from git+https://github.com/sdiebolt/jupyagent jupyagent
```

Or install it permanently:

```bash
uv tool install git+https://github.com/sdiebolt/jupyagent
```

Then run:
```bash
jupyagent
```

## Usage

1. **Setup (First Run):**
   The tool will ask you to configure your **Read-Only System Path** (for the agent to read context) and your **Read-Write Workspace** (where the agent saves files).

2. **Dashboard:**
   - **Start Services:** Launches Jupyter Lab and the MCP Server in the background.
   - **Launch Agent:** Drops you into the interactive Opencode Agent shell inside the Docker container.
   - **Open Jupyter:** Opens the Jupyter Lab interface in your browser.

## Security Note
API Keys are **not** stored in the configuration file. You must set the `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`) environment variable in your shell before running `jupyagent`. The tool passes these variables directly to the Docker container at runtime.
