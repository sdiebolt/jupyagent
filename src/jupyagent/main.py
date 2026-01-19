#!/usr/bin/env python3
import json
import os
import platform
import subprocess
import sys
import webbrowser
from pathlib import Path

try:
    from textual import on, work
    from textual.app import App, ComposeResult
    from textual.containers import Container
    from textual.screen import Screen
    from textual.widgets import (
        Button,
        Footer,
        Header,
        Input,
        Label,
        Log,
        Static,
    )
except ImportError:
    print("Error: 'textual' library is required.")
    sys.exit(1)

# --- Constants ---
APP_NAME = "jupyagent"
CONFIG_DIR = Path.home() / f".{APP_NAME}"
COMPOSE_FILE = CONFIG_DIR / "docker-compose.yml"
ENV_FILE = CONFIG_DIR / ".env"
CONFIG_JSON = CONFIG_DIR / "config.json"

# --- Logic & Helpers ---


def check_docker():
    try:
        subprocess.run(
            ["docker", "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return True
    except Exception:
        return False


def load_config():
    if CONFIG_JSON.exists():
        with open(CONFIG_JSON, "r") as f:
            return json.load(f)
    return None


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_JSON, "w") as f:
        json.dump(config, f, indent=2)


def generate_docker_files(config):
    agent_dir = CONFIG_DIR / "agent"
    agent_dir.mkdir(exist_ok=True)

    # Always Opencode now
    dockerfile_content = """FROM python:3.10-slim
WORKDIR /workspace
RUN pip install requests sseclient-py anthropic
CMD ["python", "-c", "import time; print('Opencode Agent Started. (Placeholder)'); time.sleep(9999)"]
"""

    with open(agent_dir / "Dockerfile", "w") as f:
        f.write(dockerfile_content)

    with open(ENV_FILE, "w") as f:
        f.write(f"JUPYTER_TOKEN={config.get('jupyter_token', 'secure-token')}\n")
        f.write(f"API_KEY={config.get('api_key', '')}\n")
        f.write(f"RO_PATH={config['ro_path']}\n")
        f.write(f"RW_PATH={config['rw_path']}\n")

    # Pass ANTHROPIC_API_KEY from host to container
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
    volumes:
      - ${RO_PATH}:/mnt/ro_data:ro
      - ${RW_PATH}:/workspace:rw
    environment:
      - ANTHROPIC_API_KEY=${API_KEY}
      - OPENAI_API_KEY=${API_KEY}
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


def check_service_status():
    if not COMPOSE_FILE.exists():
        return "Not Configured"
    try:
        # Simple check using docker compose ps
        res = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "ps", "--format", "json"],
            cwd=CONFIG_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if "jupyter" in res.stdout and "running" in res.stdout.lower():
            return "Running"
        return "Stopped"
    except Exception:
        return "Error"


# --- Screens ---


class SetupScreen(Screen):
    CSS = """
    Screen { align: center middle; }
    Container { width: 60; border: solid green; padding: 1 2; background: $surface; }
    Label { margin-top: 1; }
    Input { margin-bottom: 1; }
    Button { width: 100%; margin-top: 2; }
    """

    def compose(self) -> ComposeResult:
        defaults = {
            "ro_path": "C:\\" if platform.system() == "Windows" else "/",
            "rw_path": str(Path.home() / "llm-workspace"),
        }

        yield Container(
            Label("[b]JupyAgent Setup[/b]", classes="header"),
            # Re-enabled API Key Input
            Label("API Key:"),
            Input(placeholder="sk-...", password=True, id="api_key"),
            Label("Read-Only Path (System Drive):"),
            Input(value=defaults["ro_path"], id="ro_path"),
            Label("Read-Write Path (Workspace):"),
            Input(value=defaults["rw_path"], id="rw_path"),
            Button("Save & Install", variant="primary", id="save_btn"),
        )

    @on(Button.Pressed, "#save_btn")
    def on_save(self):
        config = {
            "agent_type": "opencode",
            "api_key": self.query_one("#api_key", Input).value,
            "ro_path": str(Path(self.query_one("#ro_path", Input).value).resolve()),
            "rw_path": str(Path(self.query_one("#rw_path", Input).value).resolve()),
            "jupyter_token": "token123",
        }

        # Create workspace
        Path(config["rw_path"]).mkdir(parents=True, exist_ok=True)

        save_config(config)
        generate_docker_files(config)

        self.app.push_screen(BuildScreen(config))


class BuildScreen(Screen):
    CSS = """
    Screen { align: center middle; }
    Container { width: 80; height: 20; border: solid blue; background: $surface; }
    Log { height: 1fr; border: solid gray; }
    """

    def __init__(self, config):
        super().__init__()
        self.config = config

    def compose(self) -> ComposeResult:
        yield Container(
            Label("Building Environment... Please wait."), Log(id="build_log")
        )

    def on_mount(self):
        self.run_build()

    @work(thread=True)
    def run_build(self):
        log = self.query_one(Log)
        try:
            # Pass current env to ensure we don't lose anything vital, though build shouldn't need keys
            process = subprocess.Popen(
                ["docker", "compose", "-f", str(COMPOSE_FILE), "build"],
                cwd=CONFIG_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            for line in process.stdout:
                self.app.call_from_thread(log.write, line.strip())

            process.wait()
            if process.returncode == 0:
                self.app.call_from_thread(self.app.switch_mode, "dashboard")
            else:
                self.app.call_from_thread(log.write, "Build Failed!")
        except Exception as e:
            self.app.call_from_thread(log.write, f"Error: {e}")


class DashboardScreen(Screen):
    CSS = """
    Screen { align: center middle; }
    Container { width: 60; border: solid green; padding: 1 2; background: $surface; }
    .status { margin-bottom: 2; text-align: center; color: yellow; }
    Button { margin-bottom: 1; width: 100%; }
    .running { color: green; }
    .stopped { color: red; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Label("JupyAgent Control Panel", classes="header"),
            Static("Status: Checking...", id="status", classes="status"),
            Button("Start Services", id="start_btn", variant="success"),
            Button("Stop Services", id="stop_btn", variant="error"),
            Static("", style="height: 1"),  # Spacer
            Button(
                "Launch Agent Terminal",
                id="launch_btn",
                variant="primary",
                disabled=True,
            ),
            Button(
                "Open Jupyter Lab", id="open_jupyter", variant="default", disabled=True
            ),
            Static("", style="height: 1"),  # Spacer
            Button("Exit", id="exit_btn"),
        )
        yield Footer()

    def on_mount(self):
        self.check_status_periodic()
        self.set_interval(5, self.check_status_periodic)

    def check_status_periodic(self):
        status = check_service_status()
        lbl = self.query_one("#status", Static)
        start_btn = self.query_one("#start_btn", Button)
        stop_btn = self.query_one("#stop_btn", Button)
        launch_btn = self.query_one("#launch_btn", Button)
        jupyter_btn = self.query_one("#open_jupyter", Button)

        if status == "Running":
            lbl.update(f"Status: [green]Running[/green]")
            start_btn.disabled = True
            stop_btn.disabled = False
            launch_btn.disabled = False
            jupyter_btn.disabled = False
        else:
            lbl.update(f"Status: [red]{status}[/red]")
            start_btn.disabled = False
            stop_btn.disabled = True
            launch_btn.disabled = True
            jupyter_btn.disabled = True

    @on(Button.Pressed, "#start_btn")
    def action_start(self):
        self.notify("Starting services...")
        self.run_docker_cmd(["up", "-d", "jupyter", "mcp-server"])

    @on(Button.Pressed, "#stop_btn")
    def action_stop(self):
        self.notify("Stopping services...")
        self.run_docker_cmd(["down"])

    @on(Button.Pressed, "#open_jupyter")
    def action_open_jupyter(self):
        config = load_config()
        if config:
            token = config.get("jupyter_token", "token123")
            url = f"http://localhost:8888/lab?token={token}"
            webbrowser.open(url)
            self.notify(f"Opened {url}")
        else:
            self.notify("Config missing", severity="error")

    @on(Button.Pressed, "#launch_btn")
    def action_launch(self):
        # We need to suspend the TUI to run the interactive shell
        self.app.suspend_application_mode()
        try:
            print("Launching Agent Shell... (Type 'exit' or Ctrl+C to return)")
            # Pass environment variables to the subprocess so docker compose can pick them up
            subprocess.run(
                ["docker", "compose", "-f", str(COMPOSE_FILE), "run", "--rm", "agent"],
                cwd=CONFIG_DIR,
                env=os.environ.copy(),  # Important: Pass current env (with API keys) to docker compose
            )
        except Exception as e:
            print(f"Error: {e}")
            input("Press Enter to continue...")
        finally:
            self.app.resume_application_mode()

    @on(Button.Pressed, "#exit_btn")
    def action_exit(self):
        self.app.exit()

    @work(thread=True)
    def run_docker_cmd(self, args):
        try:
            # Pass environment variables here too
            subprocess.run(
                ["docker", "compose", "-f", str(COMPOSE_FILE)] + args,
                cwd=CONFIG_DIR,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=os.environ.copy(),
            )
            self.app.call_from_thread(self.check_status_periodic)
            action = "Started" if "up" in args else "Stopped"
            self.app.call_from_thread(self.notify, f"Services {action} successfully!")
        except Exception as e:
            self.app.call_from_thread(self.notify, f"Error: {e}", severity="error")


class JupyAgentApp(App):
    TITLE = "JupyAgent"
    MODES = {"setup": SetupScreen, "dashboard": DashboardScreen}

    def on_mount(self):
        if not check_docker():
            print("Error: Docker is not installed or running.")
            self.exit()
            return

        config = load_config()
        if config:
            self.switch_mode("dashboard")
        else:
            self.switch_mode("setup")


def run():
    app = JupyAgentApp()
    app.run()
