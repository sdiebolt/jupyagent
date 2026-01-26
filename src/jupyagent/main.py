#!/usr/bin/env python3
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from importlib import metadata, resources
from pathlib import Path
from typing import Optional


def get_version() -> str:
    """Get the current package version."""
    try:
        return metadata.version("jupyagent")
    except metadata.PackageNotFoundError:
        return "dev"

try:
    import questionary
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt
    from rich.table import Table
    from rich.theme import Theme
except ImportError:
    print("Error: 'rich' and 'questionary' libraries are required.")
    sys.exit(1)


def open_browser(url: str) -> None:
    """Open a URL in the browser without printing messages."""
    try:
        if platform.system() == "Darwin":
            subprocess.run(
                ["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        elif platform.system() == "Windows":
            subprocess.run(
                ["start", url],
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:  # Linux
            subprocess.run(
                ["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
    except (FileNotFoundError, OSError):
        # Fallback if browser command is missing (common in WSL or headless servers)
        # We use print because 'console' might not be fully initialized or accessible depending on scope,
        # though it is global. Using print is safe.
        print(f"\nUnable to open browser automatically. Please open: {url}")


# --- Constants ---
APP_NAME = "jupyagent"
CONFIG_DIR = Path.home() / f".{APP_NAME}"
COMPOSE_FILE = CONFIG_DIR / "docker-compose.yml"
ENV_FILE = CONFIG_DIR / ".env"
CONFIG_JSON = CONFIG_DIR / "config.json"
DEFAULT_TOKEN = "jupyagent"

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
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
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


def get_docker_file_content(filename: str) -> str:
    """Read a docker config file from the package."""
    try:
        return resources.files("jupyagent.docker").joinpath(filename).read_text()
    except Exception:
        # Fallback for development: read from source directory
        docker_dir = Path(__file__).parent / "docker"
        return (docker_dir / filename).read_text()


def generate_docker_files(config: dict):
    """Generate Docker configuration files for JupyAgent."""
    # Create jupyter directory for Docker build context
    jupyter_dir = CONFIG_DIR / "jupyter"
    jupyter_dir.mkdir(exist_ok=True)

    # Copy all docker files from package to build context
    docker_files = [
        "Dockerfile",
        "supervisord.conf",
        "start.sh",
        "opencode.json.template",
        "register-kernel.sh",
        "run-jupyter-mcp.sh",
        "jupyter_settings.json",
    ]

    for filename in docker_files:
        content = get_docker_file_content(filename)
        dest_path = jupyter_dir / filename
        with open(dest_path, "w", newline="\n", encoding="utf-8") as f:
            f.write(content)
        # Make scripts executable
        if filename.endswith(".sh"):
            os.chmod(dest_path, 0o755)

    # Create opencode directories for persistent storage
    opencode_config_dir = CONFIG_DIR / "opencode_config"
    opencode_data_dir = CONFIG_DIR / "opencode_data"
    opencode_config_dir.mkdir(exist_ok=True)
    opencode_data_dir.mkdir(exist_ok=True)

    # Create claude directory for persistent storage (~/.claude/.credentials.json)
    claude_config_dir = CONFIG_DIR / "claude_config"
    claude_config_dir.mkdir(exist_ok=True)

    # Get configuration values
    ro_path = config["ro_path"]
    rw_path = config["rw_path"]
    jupyter_token = config.get("jupyter_token", DEFAULT_TOKEN)
    agent_config_path = str(opencode_config_dir.resolve())
    agent_data_path = str(opencode_data_dir.resolve())
    claude_config_path = str(claude_config_dir.resolve())

    # .env file
    with open(ENV_FILE, "w", newline="\n", encoding="utf-8") as f:
        f.write(f"JUPYTER_TOKEN={jupyter_token}\n")
        f.write(f"RO_PATH={ro_path}\n")
        f.write(f"RW_PATH={rw_path}\n")

    # docker-compose.yml
    compose_content = f"""services:
  jupyagent:
    image: jupyagent
    container_name: jupyagent
    build: ./jupyter
    ports:
      - "8888:8888"  # Jupyter Lab
      - "8282:8080"  # ttyd Web Terminal
      - "3000:3000"  # Opencode UI
      - "1455:1455"  # Opencode OAuth callback
    environment:
      - JUPYTER_TOKEN={jupyter_token}
      - CLAUDE_CONFIG_DIR=/home/jovyan/.claude
    volumes:
      - {ro_path}:/mnt/ro_data:ro
      - {rw_path}:/workspace:rw
      - {agent_config_path}:/home/jovyan/.config/opencode:rw
      - {agent_data_path}:/home/jovyan/.local/share/opencode:rw
      - {claude_config_path}:/home/jovyan/.claude:rw
"""
    with open(COMPOSE_FILE, "w", newline="\n", encoding="utf-8") as f:
        f.write(compose_content)


def cmd_open_web_terminal() -> str:
    url = "http://localhost:8282"
    console.print(f"Opening Web Terminal: [link]{url}[/link]")
    open_browser(url)
    return f"[info]Opened Web Terminal at {url}[/info]"


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
        # Check for running container
        return "jupyagent" in res.stdout and "running" in res.stdout.lower()
    except Exception:
        return False


# --- Commands ---


def show_help():
    """Display help/about information."""
    console.clear()
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]🤖 About JupyAgent[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()

    help_text = """[bold]What is JupyAgent?[/bold]

JupyAgent creates a secure, containerized environment for AI coding agents to work with Jupyter notebooks. It combines Jupyter Lab, AI agents (OpenCode & Claude Code), and development tools in a single Docker container.

[bold]Key Components:[/bold]

• [cyan]Jupyter Lab[/cyan] - Interactive notebook environment where agents can execute code
• [cyan]OpenCode & Claude Code[/cyan] - AI coding agents that can write and run code
• [cyan]Jupyter MCP Server[/cyan] - Model Context Protocol server that lets agents interact with Jupyter notebooks in real-time
• [cyan]Web Terminal[/cyan] - Browser-based terminal for direct access to the container
• [cyan]Dev Tools[/cyan] - git, vim, nano, build-essential, and more

[bold]Path Configuration:[/bold]

• [green]Read-Only Path[/green] - Directory the agents can read but not modify (e.g., your existing codebase or data). Mounted at [dim]/mnt/ro_data[/dim] inside the container.

• [yellow]Read-Write Path[/yellow] - Directory where agents can create and modify files (e.g., your project workspace). Mounted at [dim]/workspace[/dim] inside the container.

[bold]How It Works:[/bold]

1. Both OpenCode and Claude Code connect to the Jupyter MCP server
2. Agents can create notebooks, execute code, and see results in real-time
3. All work happens in the isolated Docker container
4. Your files in the read-write path are preserved between sessions

[bold]Authentication:[/bold]

• Jupyter Lab uses an auto-generated token (embedded in URLs)
• Web terminal has no authentication (localhost only)
• OpenCode and Claude Code use persistent authentication

For more info: [link]https://github.com/sdiebolt/jupyagent[/link]"""

    console.print(Panel(help_text, border_style="cyan", padding=(1, 2)))
    console.print()
    Prompt.ask("[dim]Press Enter to continue[/dim]", default="")


def cmd_setup():
    console.clear()
    console.print()
    console.print(Panel.fit("[bold]🔧 JupyAgent Setup[/bold]", border_style="blue"))

    # Load existing config if available
    existing_config = load_config()

    defaults = {
        "ro_path": existing_config.get("ro_path", "/") if existing_config else "/",
        "rw_path": existing_config.get("rw_path", str(Path.home() / "jupyagent"))
        if existing_config
        else str(Path.home() / "jupyagent"),
    }

    # If paths are already configured, ask if user wants to change them
    if existing_config and existing_config.get("ro_path") and existing_config.get("rw_path"):
        console.print("[bold]Current paths:[/bold]")
        console.print(f"  [info]Read-Only:[/info]  {defaults['ro_path']}")
        console.print(f"  [info]Workspace:[/info]  {defaults['rw_path']}")
        console.print()

        if Confirm.ask("Keep existing paths?", default=True):
            ro_path = defaults["ro_path"]
            rw_path = defaults["rw_path"]
        else:
            ro_path = Prompt.ask(
                "Read-Only System Path (Context for Agent)", default=defaults["ro_path"]
            )
            rw_path = Prompt.ask(
                "Read-Write Workspace Path (Agent Saves Here)", default=defaults["rw_path"]
            )
    else:
        # First-time setup: always prompt for paths
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
        "version": get_version(),
        "agent_type": "opencode",
        "ro_path": str(Path(ro_path).resolve()),
        "rw_path": str(Path(rw_path).resolve()),
        "jupyter_token": DEFAULT_TOKEN,
    }

    try:
        Path(config["rw_path"]).mkdir(parents=True, exist_ok=True)
        save_config(config)
        generate_docker_files(config)

        # Load .env to pass to subprocess
        env = os.environ.copy()
        with open(ENV_FILE, "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    env[key] = value

        console.print("\n[highlight]Building Docker environment...[/highlight]")
        subprocess.run(
            DOCKER_CMD
            + [
                "compose",
                "--env-file",
                str(ENV_FILE),
                "-f",
                str(COMPOSE_FILE),
                "build",
            ],
            cwd=CONFIG_DIR,
            env=env,
            check=True,
        )
        console.print("[success]Setup Complete![/success]")
    except Exception as e:
        console.print(f"[error]Setup Failed:[/error] {e}")
        sys.exit(1)


def cmd_start() -> str:
    if not CONFIG_JSON.exists():
        console.print("[error]Not configured.[/error] Run setup first.")
        cmd_setup()

    try:
        # Load .env manually to pass to subprocess
        env = os.environ.copy()
        if ENV_FILE.exists():
            with open(ENV_FILE, "r") as f:
                for line in f:
                    if "=" in line:
                        key, value = line.strip().split("=", 1)
                        env[key] = value

        # Clean up stale token file before starting
        config = load_config() or {}
        rw_path = config.get("rw_path")
        token_file = None
        if rw_path:
            token_file = Path(rw_path) / "TOKEN.txt"
            if token_file.exists():
                token_file.unlink()

        with console.status(
            "[highlight]Starting services (Jupyter + ttyd + Opencode)...[/highlight]"
        ):
            subprocess.run(
                DOCKER_CMD
                + [
                    "compose",
                    "--env-file",
                    str(ENV_FILE),
                    "-f",
                    str(COMPOSE_FILE),
                    "up",
                    "-d",
                ],
                cwd=CONFIG_DIR,
                env=env,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Wait for token file to be created to ensure all services are started.
            token = None
            if token_file:
                for _ in range(30):
                    if token_file.exists():
                        content = token_file.read_text().strip()
                        if content:
                            token = content
                            break
                    time.sleep(1)

        # Open browsers after spinner is done
        if token:
            console.print("[info]Opening web interfaces...[/info]")
            open_browser(f"http://localhost:8888/lab?token={token}")
            open_browser("http://localhost:8282")
            open_browser("http://localhost:3000")

        return "[success]Services started successfully.[/success]"
    except subprocess.CalledProcessError:
        return "[error]Failed to start services.[/error]"


def cmd_launch_agent() -> str:
    console.print("[highlight]Opening Agent Web Interface...[/highlight]")
    console.print("[info]Once running, open: http://localhost:3000[/info]")
    try:
        open_browser("http://localhost:3000")
        return "[success]Opened web browser.[/success]"
    except subprocess.CalledProcessError:
        return "[error]Failed to start Agent service.[/error]"


def cmd_open_jupyter() -> str:
    config = load_config()
    if config:
        # Read token from file (generated by Zellij at container startup)
        token_file = Path(config.get("rw_path", ".")) / "TOKEN.txt"
        token = DEFAULT_TOKEN
        if token_file.exists():
            try:
                content = token_file.read_text().strip()
                if content:
                    token = content
            except Exception:
                pass
        url = f"http://localhost:8888/lab?token={token}"
        console.print(f"Opening Jupyter: [link]{url}[/link]")
        open_browser(url)
        return f"[info]Opened Jupyter at {url}[/info]"
    return "[error]Config not found.[/error]"


def cmd_stop() -> str:
    if not CONFIG_JSON.exists():
        return "[warning]Not set up.[/warning]"
    with console.status("[warning]Stopping services...[/warning]"):
        subprocess.run(
            DOCKER_CMD + ["compose", "-f", str(COMPOSE_FILE), "down"],
            cwd=CONFIG_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return "[success]Services stopped.[/success]"


def cmd_dashboard(msg=""):
    """Simple Menu-based Dashboard"""
    while True:
        running = is_service_running()
        status = (
            "[bold green]● Running[/bold green]"
            if running
            else "[bold red]○ Stopped[/bold red]"
        )

        console.clear()
        console.print()
        console.print(
            Panel(
                f"🤖 [bold cyan]JupyAgent[/bold cyan]  {status}",
                border_style="cyan",
                padding=(0, 2),
            )
        )

        if msg:
            console.print(f"\n{msg}")
            msg = ""

        if running:
            config = load_config() or {}
            token_file = Path(config.get("rw_path", ".")) / "TOKEN.txt"
            token = None

            if token_file.exists():
                try:
                    content = token_file.read_text().strip()
                    if content:
                        token = content
                except Exception:
                    pass

            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column("Service", style="bold")
            table.add_column("URL")

            if token:
                table.add_row(
                    "Jupyter Lab", f"[link]http://localhost:8888/lab?token={token}[/link]"
                )
            else:
                table.add_row(
                    "Jupyter Lab", "[link]http://localhost:8888[/link] [dim](starting...)[/dim]"
                )

            table.add_row(
                "Web Terminal",
                "[link]http://localhost:8282[/link]",
            )
            table.add_row("Opencode", "[link]http://localhost:3000[/link]")

            console.print()
            console.print(
                Panel(
                    table,
                    border_style="green",
                    title="[bold]Services[/bold]",
                    padding=(1, 2),
                )
            )

        console.print()

        toggle_option = (
            questionary.Choice("⏹️ Stop Services", value="toggle")
            if running
            else questionary.Choice("▶️ Start Services", value="toggle")
        )

        choices = [
            toggle_option,
            questionary.Separator("─" * 30),
            questionary.Choice("📓 Open Jupyter Lab", value="jupyter"),
            questionary.Choice("💻 Open Web Terminal", value="terminal"),
            questionary.Choice("🤖 Open Opencode", value="opencode"),
            questionary.Separator("─" * 30),
            questionary.Choice("⚙️ Re-configure", value="config"),
            questionary.Choice("ℹ️  Help", value="help"),
            questionary.Choice("❌ Exit", value="exit"),
        ]

        choice = questionary.select(
            "",
            choices=choices,
            style=questionary.Style(
                [
                    ("qmark", "hidden"),
                    ("question", "bold"),
                    ("answer", "fg:#00d7ff bold"),
                    ("pointer", "fg:#00d7ff bold"),
                    ("highlighted", "fg:#00d7ff bold"),
                    ("selected", "fg:#00d7ff"),
                    ("separator", "fg:#555555"),
                    ("instruction", "fg:#555555"),
                    ("text", ""),
                    ("disabled", "fg:#555555"),
                ]
            ),
            instruction="(↑/↓ to move, Enter to select)",
        ).ask()

        if choice == "toggle":
            if running:
                msg = cmd_stop()
            else:
                msg = cmd_start()
        elif choice == "jupyter":
            msg = cmd_open_jupyter()
        elif choice == "terminal":
            msg = cmd_open_web_terminal()
        elif choice == "opencode":
            msg = cmd_launch_agent()
        elif choice == "config":
            cmd_setup()
            msg = "[success]Configuration updated.[/success]"
        elif choice == "help":
            show_help()
        elif choice == "exit":
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
        # First-time setup: show help
        show_help()
        cmd_setup()
    else:
        # Check for version mismatch
        config = load_config()
        current_version = get_version()
        config_version = config.get("version") if config else None

        if config_version != current_version:
            console.print(
                f"[warning]New version detected:[/warning] {config_version or 'unknown'} → {current_version}"
            )
            if Confirm.ask("Re-configure to apply updates?", default=True):
                cmd_setup()

    # 3. Launch Dashboard
    cmd_dashboard()


if __name__ == "__main__":
    run()
