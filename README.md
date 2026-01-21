# 🤖 JupyAgent

**JupyAgent** is a CLI tool that installs a containerized environment running web UIs
from Jupyter server, an LLM agent ([OpenCode](https://opencode.ai/)), and a terminal
([Zellij](https://zellij.dev/)).

## Features
- **🛡️ Secure Sandbox:** Agents operate in an isolated Docker container with controlled
  read/write access.
- **⚡ Real-time agentic coding in Jupyter:** Watch the agent write and execute code in
  Jupyter Lab in real-time via the MCP protocol.
- **🖥️ Integrated Stack:**
    - **Jupyter Lab:** For code execution and notebook management.
    - **OpenCode:** The AI coding agent.
    - **Zellij:** A full-featured terminal workspace accessible via the browser.
- **🚀 One-command management:** `jupyagent`, a TUI dashboard to manage the tool.

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
   - **📓 Open Jupyter Lab:** Access the notebook interface.
   - **🤖 Open Opencode:** Access the OpenCode Web UI to give instructions.
   - **💻 Open Web Terminal:** Access the Zellij terminal session.

## Architecture
JupyAgent builds a custom Docker image combining:
- `jupyter/base-notebook`
- `mcp-server-jupyter` (with collaboration support)
- `opencode` CLI/Web
- `zellij`
