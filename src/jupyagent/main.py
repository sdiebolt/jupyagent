#!/usr/bin/env python3
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import webbrowser
from importlib import resources
from pathlib import Path
from typing import Optional

try:
    import questionary
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt
    from rich.theme import Theme
except ImportError:
    print("Error: 'rich' and 'questionary' libraries are required.")
    sys.exit(1)

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
        "zellij-config.kdl",
        "register-kernel.sh",
    ]

    for filename in docker_files:
        content = get_docker_file_content(filename)
        dest_path = jupyter_dir / filename
        with open(dest_path, "w") as f:
            f.write(content)
        # Make scripts executable
        if filename.endswith(".sh"):
            os.chmod(dest_path, 0o755)

    # Create opencode directories for persistent storage
    opencode_config_dir = CONFIG_DIR / "opencode_config"
    opencode_data_dir = CONFIG_DIR / "opencode_data"
    opencode_config_dir.mkdir(exist_ok=True)
    opencode_data_dir.mkdir(exist_ok=True)

    # Get configuration values
    ro_path = config["ro_path"]
    rw_path = config["rw_path"]
    jupyter_token = config.get("jupyter_token", DEFAULT_TOKEN)
    agent_config_path = str(opencode_config_dir.resolve())
    agent_data_path = str(opencode_data_dir.resolve())

    # .env file
    with open(ENV_FILE, "w") as f:
        f.write(f"JUPYTER_TOKEN={jupyter_token}\n")
        f.write(f"RO_PATH={ro_path}\n")
        f.write(f"RW_PATH={rw_path}\n")

    # Conditional volume mount for mkcert certificates
    certs_mount = ""
    if config.get("use_mkcert"):
        certs_path = str((CONFIG_DIR / "certs").resolve())
        certs_mount = f"      - {certs_path}:/home/jovyan/.config/zellij/certs:ro\n"

    # docker-compose.yml
    compose_content = f"""services:
  jupyagent:
    build: ./jupyter
    ports:
      - "8888:8888"  # Jupyter Lab
      - "8282:8080"  # Zellij Web Terminal
      - "3000:3000"  # Opencode UI
    environment:
      - JUPYTER_TOKEN={jupyter_token}
    volumes:
      - {ro_path}:/mnt/ro_data:ro
      - {rw_path}:/workspace:rw
      - {agent_config_path}:/home/jovyan/.config/opencode:rw
      - {agent_data_path}:/home/jovyan/.local/share/opencode:rw
{certs_mount}"""
    with open(COMPOSE_FILE, "w") as f:
        f.write(compose_content)


def cmd_open_web_terminal() -> str:
    # Use the same token for Zellij web if we can get it?
    # Zellij uses its own auth, but we might want to pass the token in URL if supported?
    # Zellij doesn't support token in URL standardly, but we can try.
    # Actually, we just need to open the link.
    url = "https://localhost:8282"
    console.print(f"Opening Web Terminal: [link]{url}[/link]")
    webbrowser.open(url)
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


def cmd_setup():
    console.print(Panel.fit("🛠️  [bold]JupyAgent Setup[/bold]", border_style="blue"))

    defaults = {
        "ro_path": "C:\\\\" if platform.system() == "Windows" else "/",
        "rw_path": str(Path.home() / "jupyagent"),
    }

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
        "ro_path": str(Path(ro_path).resolve()),
        "rw_path": str(Path(rw_path).resolve()),
        "jupyter_token": DEFAULT_TOKEN,
        "use_mkcert": False,
    }

    # Optional: mkcert setup
    if shutil.which("mkcert"):
        if Confirm.ask(
            "mkcert found. Generate locally trusted SSL certificates?", default=True
        ):
            certs_dir = CONFIG_DIR / "certs"
            certs_dir.mkdir(exist_ok=True)
            try:
                subprocess.run(
                    ["mkcert", "-install"],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                subprocess.run(
                    [
                        "mkcert",
                        "-key-file",
                        str(certs_dir / "key.pem"),
                        "-cert-file",
                        str(certs_dir / "cert.pem"),
                        "localhost",
                        "127.0.0.1",
                        "::1",
                        "0.0.0.0",
                    ],
                    cwd=CONFIG_DIR,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                config["use_mkcert"] = True
                console.print("[success]Certificates generated![/success]")
            except Exception as e:
                console.print(
                    f"[warning]Failed to generate certs: {e}. Falling back to self-signed.[/warning]"
                )

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

    console.print(
        "[highlight]Starting services (Jupyter + Zellij + Opencode)...[/highlight]"
    )
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
            token_file = Path(rw_path) / "ZELLIJ_TOKEN.txt"
            if token_file.exists():
                token_file.unlink()

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

        # Wait for token file to be created (up to 30 seconds)
        token = None
        if token_file:
            console.print("[info]Waiting for services to initialize...[/info]")
            for _ in range(30):
                if token_file.exists():
                    content = token_file.read_text().strip()
                    if content:
                        token = content
                        break
                time.sleep(1)

        # Open all three UIs in browser
        if token:
            console.print("[info]Opening web interfaces...[/info]")
            webbrowser.open(f"http://localhost:8888/lab?token={token}")
            webbrowser.open("https://localhost:8282")
            webbrowser.open("http://localhost:3000")

        return "[success]Services started successfully.[/success]"
    except subprocess.CalledProcessError:
        return "[error]Failed to start services.[/error]"


def cmd_launch_agent() -> str:
    console.print("[highlight]Opening Agent Web Interface...[/highlight]")
    console.print("[info]Once running, open: http://localhost:3000[/info]")
    try:
        webbrowser.open("http://localhost:3000")
        return "[success]Opened web browser.[/success]"
    except subprocess.CalledProcessError:
        return "[error]Failed to start Agent service.[/error]"


def cmd_open_jupyter() -> str:
    config = load_config()
    if config:
        # Read token from file (generated by Zellij at container startup)
        token_file = Path(config.get("rw_path", ".")) / "ZELLIJ_TOKEN.txt"
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
        webbrowser.open(url)
        return f"[info]Opened Jupyter at {url}[/info]"
    return "[error]Config not found.[/error]"


def cmd_stop() -> str:
    if not CONFIG_JSON.exists():
        return "[warning]Not set up.[/warning]"
    console.print("[warning]Stopping services...[/warning]")
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

        if msg:
            console.print(f"{msg}\n")
            msg = ""  # Clear after displaying

        if is_service_running():
            config = load_config() or {}
            # Read token from file (generated by Zellij at container startup)
            token_file = Path(config.get("rw_path", ".")) / "ZELLIJ_TOKEN.txt"
            token = "Waiting for token..."

            if token_file.exists():
                try:
                    content = token_file.read_text().strip()
                    if content:
                        token = content
                except Exception:
                    pass

            access_info = f"""
[bold]Access Information:[/bold]
  Jupyter Lab:    [link]http://localhost:8888/lab?token={token}[/link]
  Web Terminal:   [link]https://localhost:8282[/link] (Accept cert warning)
  Opencode UI:    [link]http://localhost:3000[/link]
  Token:          [bold green]{token}[/bold green]
"""
            console.print(
                Panel(
                    access_info,
                    border_style="green",
                    title="Services Active",
                )
            )
            console.print("")

        choices = [
            "Start Services",
            "Stop Services",
            "Launch Agent Web UI",
            "Open Jupyter Lab",
            "Open Web Terminal",
            "Re-configure",
            "Exit",
        ]

        choice = questionary.select(
            "Choose an action:",
            choices=choices,
            style=questionary.Style(
                [
                    ("qmark", "fg:#673ab7 bold"),
                    ("question", "bold"),
                    ("answer", "fg:#f44336 bold"),
                    ("pointer", "fg:#673ab7 bold"),
                    ("highlighted", "fg:#673ab7 bold"),
                    ("selected", "fg:#cc5454"),
                    ("separator", "fg:#cc5454"),
                    ("instruction", ""),
                    ("text", ""),
                    ("disabled", "fg:#858585 italic"),
                ]
            ),
        ).ask()

        if choice == "Start Services":
            msg = cmd_start()
        elif choice == "Stop Services":
            msg = cmd_stop()
        elif choice == "Launch Agent Web UI":
            msg = cmd_launch_agent()
        elif choice == "Open Jupyter Lab":
            msg = cmd_open_jupyter()
        elif choice == "Open Web Terminal":
            msg = cmd_open_web_terminal()
        elif choice == "Re-configure":
            cmd_setup()
            msg = "[success]Configuration updated.[/success]"
        elif choice == "Exit":
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
