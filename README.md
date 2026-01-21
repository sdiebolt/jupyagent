# 🤖 JupyAgent

**JupyAgent** is a CLI tool that installs a containerized environment to run web UIs for
a Jupyter server, an LLM agent (Opencode), and a terminal. It unifies Jupyter Lab, a
Real-time Jupyter MCP Server, the **Opencode** Agent, and a Zellij web terminal into a
single, easy-to-manage Docker sandbox.

## Features
- **🛡️ Secure Sandbox:** Agents operate in an isolated Docker container with controlled read/write access.
- **⚡ Real-time Collaboration:** Watch the agent write and execute code in Jupyter Lab in real-time via the MCP protocol.
- **🖥️ Integrated Stack:**
    - **Jupyter Lab:** For code execution and notebook management.
    - **Opencode Agent:** The AI coding agent (Web UI).
    - **Zellij:** A full-featured terminal workspace accessible via browser.
- **🚀 One-Command Management:** A TUI dashboard to manage the entire lifecycle.

## Prerequisites
- **Docker:** Must be installed and running.
- **uv:** Recommended for running the tool. [Install uv](https://docs.astral.sh/uv/getting-started/installation/)

## Quick Start

Run JupyAgent directly:

```bash
uvx --from git+https://github.com/sdiebolt/jupyagent jupyagent
```

## Usage

1. **Setup:** On first run, configure your workspace:
   - **Context Path (Read-Only):** Directory the agent can read (e.g., your project root).
   - **Workspace Path (Read-Write):** Directory where the agent creates files.

2. **Dashboard:**
   - **▶️ Start/Stop Services:** Toggle the background Docker container.
   - **📓 Open Jupyter Lab:** Access the notebook interface.
   - **🤖 Open Opencode:** Access the Agent Web UI to give instructions.
   - **💻 Open Web Terminal:** Access the Zellij terminal session.

## Architecture
JupyAgent builds a custom Docker image combining:
- `jupyter/base-notebook`
- `mcp-server-jupyter` (with collaboration support)
- `opencode` CLI/Web
- `zellij`
