#!/usr/bin/env python3
import json
import os
import platform
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Optional

try:
    from rich.console import Console
    from rich.prompt import Prompt, Confirm
    from rich.panel import Panel
    from rich.markdown import Markdown
    from rich.theme import Theme
except ImportError:
    print("Error: 'rich' library is required.")
    sys.exit(1)

# --- Constants ---
APP_NAME = "jupyagent"
CONFIG_DIR = Path.home() / f".{APP_NAME}"
COMPOSE_FILE = CONFIG_DIR / "docker-compose.yml"
ENV_FILE = CONFIG_DIR / ".env"
CONFIG_JSON = CONFIG_DIR / "config.json"

# --- Styling ---
custom_theme = Theme(
    {
        "info": "dim cyan",
        "warning": "yellow",
        "error": "bold red",
        "success": "bold green",
        "highlight": "magenta",
    }
)
console = Console(theme=custom_theme)

# --- Globals ---
DOCKER_CMD = ["docker"]

# --- Logic & Helpers ---


def detect_docker_command():
    """Detects if we need to use 'sudo docker' or just 'docker'."""
    global DOCKER_CMD

    # Try standard docker
    try:
        subprocess.run(
            ["docker", "info"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        DOCKER_CMD = ["docker"]
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Try sudo docker
    if platform.system() == "Linux":
        try:
            subprocess.run(
                ["sudo", "docker", "info"],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            DOCKER_CMD = ["sudo", "docker"]
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

    return False


def check_docker() -> bool:
    try:
        # Check CLI presence
        subprocess.run(
            ["docker", "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_docker_running() -> bool:
    # Use the detected command
    try:
        subprocess.run(
            DOCKER_CMD + ["info"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def load_config() -> Optional[dict]:
    if CONFIG_JSON.exists():
        try:
            with open(CONFIG_JSON, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return None
    return None


def save_config(config: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_JSON, "w") as f:
        json.dump(config, f, indent=2)


def generate_docker_files(config: dict):
    agent_dir = CONFIG_DIR / "agent"
    agent_dir.mkdir(exist_ok=True)

    # Agent Dockerfile (Opencode)
    dockerfile_content = """FROM python:3.10-slim
WORKDIR /workspace
RUN pip install opencode
CMD ["opencode", "web"]
"""
    with open(agent_dir / "Dockerfile", "w") as f:
        f.write(dockerfile_content)

    # .env file
    with open(ENV_FILE, "w") as f:
        f.write(f"JUPYTER_TOKEN={config.get('jupyter_token', 'secure-token')}\n")
        f.write(f"API_KEY={config.get('api_key', '')}\n")
        f.write(f"RO_PATH={config['ro_path']}\n")
        f.write(f"RW_PATH={config['rw_path']}\n")

    # docker-compose.yml
    compose_content = """version: '3.8'

services:
  jupyter:
    image: jupyter/base-notebook:latest
    ports:
      - "8888:8888"
    environment:
      - JUPYTER_TOKEN=${JUPYTER_TOKEN}
    volumes:
      - ${RO_PATH}:/mnt/ro_data:ro
      - ${RW_PATH}:/home/jovyan/work:rw

  mcp-server:
    image: datalayer/jupyter-mcp-server:latest
    environment:
      - JUPYTER_URL=http://jupyter:8888
      - JUPYTER_TOKEN=${JUPYTER_TOKEN}
      - ALLOW_IMG_OUTPUT=true
    depends_on:
      - jupyter

  agent:
    build: ./agent
    ports:
      - "3000:3000"
    volumes:
      - ${RO_PATH}:/mnt/ro_data:ro
      - ${RW_PATH}:/workspace:rw
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - JUPYTER_URL=http://jupyter:8888
      - JUPYTER_TOKEN=${JUPYTER_TOKEN}
    working_dir: /workspace
    stdin_open: true 
    tty: true
    depends_on:
      - mcp-server
"""
    with open(COMPOSE_FILE, "w") as f:
        f.write(compose_content)


def is_service_running() -> bool:
    if not COMPOSE_FILE.exists():
        return False
    try:
        res = subprocess.run(
            DOCKER_CMD + ["compose", "-f", str(COMPOSE_FILE), "ps", "--format", "json"],
            cwd=CONFIG_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Rudimentary check: simply look for running container name
        return "jupyter" in res.stdout and "running" in res.stdout.lower()
    except Exception:
        return False


# --- Commands ---


def cmd_setup():
    console.print(Panel.fit("🛠️  [bold]JupyAgent Setup[/bold]", border_style="blue"))

    defaults = {
        "ro_path": "C:\\" if platform.system() == "Windows" else "/",
        "rw_path": str(Path.home() / "jupyagent"),
    }

    # API Key
    api_key = Prompt.ask(
        "Enter your [bold]Anthropic API Key[/bold] (stored locally)", password=True
    )
    if not api_key:
        console.print(
            "[warning]No API Key provided. Agent may not function correctly.[/warning]"
        )

    # Paths
    ro_path = Prompt.ask(
        "Read-Only System Path (Context for Agent)", default=defaults["ro_path"]
    )
    rw_path = Prompt.ask(
        "Read-Write Workspace Path (Agent Saves Here)", default=defaults["rw_path"]
    )

    # Confirmation
    console.print("\n[bold]Configuration Summary:[/bold]")
    console.print(f"  [info]Read-Only:[/info]  {ro_path}")
    console.print(f"  [info]Workspace:[/info]  {rw_path}")

    if not Confirm.ask("Proceed with installation?", default=True):
        console.print("[error]Aborted.[/error]")
        sys.exit(0)

    # Processing
    config = {
        "agent_type": "opencode",
        "api_key": api_key,
        "ro_path": str(Path(ro_path).resolve()),
        "rw_path": str(Path(rw_path).resolve()),
        "jupyter_token": "token123",
    }

    try:
        Path(config["rw_path"]).mkdir(parents=True, exist_ok=True)
        save_config(config)
        generate_docker_files(config)

        console.print("\n[highlight]Building Docker environment...[/highlight]")
        subprocess.run(
            DOCKER_CMD + ["compose", "-f", str(COMPOSE_FILE), "build"],
            cwd=CONFIG_DIR,
            check=True,
        )
        console.print("[success]Setup Complete![/success]")
    except Exception as e:
        console.print(f"[error]Setup Failed:[/error] {e}")
        sys.exit(1)


def cmd_start():
    if not CONFIG_JSON.exists():
        console.print("[error]Not configured.[/error] Run setup first.")
        cmd_setup()

    console.print(
        "[highlight]Starting background services (Jupyter + MCP)...[/highlight]"
    )
    try:
        # We need to pass current env to docker-compose so it gets the API keys if user set them in shell,
        # OR relies on the .env file we generated.
        subprocess.run(
            DOCKER_CMD
            + [
                "compose",
                "-f",
                str(COMPOSE_FILE),
                "up",
                "-d",
                "jupyter",
                "mcp-server",
            ],
            cwd=CONFIG_DIR,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        console.print("[success]Services started.[/success]")
    except subprocess.CalledProcessError:
        console.print("[error]Failed to start services.[/error]")
        sys.exit(1)


def cmd_launch_agent():
    console.print("[highlight]Starting Agent Web Interface...[/highlight]")
    console.print("[info]Once running, open: http://localhost:3000[/info]")
    try:
        subprocess.run(
            DOCKER_CMD + ["compose", "-f", str(COMPOSE_FILE), "up", "-d", "agent"],
            cwd=CONFIG_DIR,
            env=os.environ.copy(),
        )
        webbrowser.open("http://localhost:3000")
    except subprocess.CalledProcessError:
        console.print("[error]Failed to start Agent service.[/error]")


def cmd_open_jupyter():
    config = load_config()
    if config:
        token = config.get("jupyter_token", "token123")
        url = f"http://localhost:8888/lab?token={token}"
        console.print(f"Opening Jupyter: [link]{url}[/link]")
        webbrowser.open(url)


def cmd_stop():
    if not CONFIG_JSON.exists():
        return
    console.print("[warning]Stopping services...[/warning]")
    subprocess.run(
        DOCKER_CMD + ["compose", "-f", str(COMPOSE_FILE), "down"],
        cwd=CONFIG_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    console.print("[success]Stopped.[/success]")


def cmd_dashboard():
    """Simple Menu-based Dashboard"""
    while True:
        # Status Check
        status = (
            "[bold green]Running[/bold green]"
            if is_service_running()
            else "[bold red]Stopped[/bold red]"
        )

        console.clear()
        console.print(
            Panel.fit(
                f"🤖 [bold]JupyAgent Dashboard[/bold]   Status: {status}",
                border_style="blue",
            )
        )

        console.print("1. [bold green]Start[/bold green] Services")
        console.print("2. [bold red]Stop[/bold red] Services")
        console.print("3. [bold cyan]Launch[/bold cyan] Agent Web UI")
        console.print("4. [bold yellow]Open[/bold yellow] Jupyter Lab")
        console.print("5. [bold]Re-configure[/bold]")
        console.print("6. [dim]Exit[/dim]")

        choice = Prompt.ask(
            "\nChoose an option", choices=["1", "2", "3", "4", "5", "6"], default="6"
        )

        if choice == "1":
            cmd_start()
            Prompt.ask("Press Enter to continue...")
        elif choice == "2":
            cmd_stop()
            Prompt.ask("Press Enter to continue...")
        elif choice == "3":
            cmd_launch_agent()
        elif choice == "4":
            cmd_open_jupyter()
            Prompt.ask("Press Enter to continue...")
        elif choice == "5":
            cmd_setup()
            Prompt.ask("Press Enter to continue...")
        elif choice == "6":
            console.print("Bye!")
            break


# --- Main Entry Point ---


def run():
    # 1. Prerequisite Checks
    detect_docker_command()
    if not check_docker():
        console.print(
            "[error]Error: Docker CLI not found.[/error] Please install Docker."
        )
        sys.exit(1)

    if not check_docker_running():
        console.print("[error]Error: Docker Daemon is not running.[/error]")
        if platform.system() == "Linux":
            console.print("[info]Try running: sudo systemctl start docker[/info]")
        elif platform.system() == "Darwin":
            console.print("[info]Please open Docker Desktop.[/info]")
        sys.exit(1)

    # 2. Logic
    if not CONFIG_JSON.exists():
        console.print("[warning]Configuration not found.[/warning]")
        cmd_setup()

    # 3. Launch Dashboard
    cmd_dashboard()


if __name__ == "__main__":
    run()
