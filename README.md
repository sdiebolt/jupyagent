# 🤖 JupyAgent

**JupyAgent** is a CLI tool that installs a containerized environment running web UIs
from Jupyter server, LLM agents ([OpenCode](https://opencode.ai/) and [Claude Code](https://claude.ai/code)),
and a web terminal ([ttyd](https://github.com/tsl0922/ttyd)).

## Features
- **🛡️ Secure Sandbox:** Agents operate in an isolated Docker container with controlled
  read/write access.
- **⚡ Real-time agentic coding in Jupyter:** Watch agents write and execute code in
  Jupyter Lab in real-time via the MCP protocol.
- **🖥️ Integrated Stack:**
    - **Jupyter Lab:** For code execution and notebook management.
    - **OpenCode & Claude Code:** AI coding agents with Jupyter MCP integration.
    - **ttyd:** Web-based terminal with no authentication required.
    - **Dev Tools:** git, vim, nano, build-essential, jq, htop, tree, and more.
- **🚀 One-command management:** `jupyagent`, a TUI dashboard to manage the tool.
- **🔓 Seamless Access:** No password prompts - click and start working.

## Prerequisites
- **[Docker](https://www.docker.com/get-started/):** Must be installed and running.
- **[uv](https://docs.astral.sh/uv/getting-started/installation/):** Recommended for
  running the tool.

## Quick Start

Run JupyAgent directly:

```bash
uvx jupyagent
```

## Usage

1. **Setup:** On first run, configure your workspace:
   - **Context Path (Read-Only):** Directory the agent can read (e.g., your data drive).
   - **Workspace Path (Read-Write):** Directory where the agent creates files (e.g.,
     your project root).

2. **Dashboard:**
   - **▶️ Start/Stop Services:** Toggle the background Docker container.
   - **📓 Open Jupyter Lab:** Access the notebook interface (auto-authenticated).
   - **🤖 Open Opencode:** Access the OpenCode Web UI to give instructions.
   - **💻 Open Web Terminal:** Access the web terminal (instant access, no login).

## Architecture
JupyAgent builds a custom Docker image combining:
- `jupyter/base-notebook`
- `mcp-server-jupyter` (with collaboration support)
- `opencode` CLI/Web
- `claude` CLI (Claude Code)
- `ttyd` web terminal
- Essential dev tools (git, vim, nano, build-essential, jq, htop, tree)
