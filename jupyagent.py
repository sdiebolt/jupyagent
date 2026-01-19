#!/usr/bin/env python3
import os
import sys
import platform
import subprocess
import argparse
import json
from pathlib import Path

# --- Constants & Defaults ---
APP_NAME = "jupyagent"
CONFIG_DIR = Path.home() / f".{APP_NAME}"
COMPOSE_FILE = CONFIG_DIR / "docker-compose.yml"
ENV_FILE = CONFIG_DIR / ".env"
CONFIG_JSON = CONFIG_DIR / "config.json"


# ANSI Colors
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def print_step(msg):
    print(f"{Colors.BLUE}[*] {msg}{Colors.ENDC}")


def print_success(msg):
    print(f"{Colors.GREEN}[+] {msg}{Colors.ENDC}")


def print_error(msg):
    print(f"{Colors.FAIL}[!] {msg}{Colors.ENDC}")


def print_header(msg):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{msg}{Colors.ENDC}")


# --- Helper Functions ---


def check_docker():
    """Verify Docker is installed and running."""
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


def get_input(prompt, default=None, hidden=False):
    """Get user input with optional default and hiding."""
    prompt_text = f"{prompt} [{default}]: " if default else f"{prompt}: "
    try:
        if hidden:
            import getpass

            val = getpass.getpass(f"{prompt}: ")
        else:
            val = input(prompt_text)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(0)

    return val if val else default


def save_config(config):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_JSON, "w") as f:
        json.dump(config, f, indent=2)


def load_config():
    if CONFIG_JSON.exists():
        with open(CONFIG_JSON, "r") as f:
            return json.load(f)
    return None


# --- Generators ---


def generate_docker_files(config):
    """Generates docker-compose.yml, .env and agent/Dockerfile in CONFIG_DIR"""

    # 1. Generate Agent Dockerfile
    agent_dir = CONFIG_DIR / "agent"
    agent_dir.mkdir(exist_ok=True)

    agent_type = config.get("agent_type", "opencode")

    dockerfile_content = ""
    if agent_type == "opencode":
        dockerfile_content = """FROM python:3.10-slim
WORKDIR /workspace
RUN pip install requests sseclient-py anthropic
# Placeholder for the actual agent logic or package installation
CMD ["python", "-c", "import time; print('Opencode Agent Started. (Placeholder)'); time.sleep(9999)"]
"""
    elif agent_type == "claude":
        # Official Claude Code might require specific setup, using a placeholder based on node
        dockerfile_content = """FROM node:20-slim
WORKDIR /workspace
RUN npm install -g @anthropic-ai/claude-code
CMD ["claude"]
"""
    elif agent_type == "gemini":
        dockerfile_content = """FROM python:3.10-slim
WORKDIR /workspace
RUN pip install google-generativeai
CMD ["bash"] 
"""

    with open(agent_dir / "Dockerfile", "w") as f:
        f.write(dockerfile_content)

    # 2. Generate .env
    with open(ENV_FILE, "w") as f:
        f.write(f"JUPYTER_TOKEN={config.get('jupyter_token', 'secure-token')}\n")
        f.write(f"API_KEY={config.get('api_key', '')}\n")
        # Docker compose expects paths to be absolute and normalized
        f.write(f"RO_PATH={config['ro_path']}\n")
        f.write(f"RW_PATH={config['rw_path']}\n")

    # 3. Generate docker-compose.yml
    # We use 'host-gateway' for linux to allow containers to talk if needed,
    # but primarily they talk via the docker network 'llm-net'.

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
      - GOOGLE_API_KEY=${API_KEY}
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


# --- Commands ---


def cmd_setup():
    print_header("JupyAgent Environment Setup")

    if not check_docker():
        print_error(
            "Docker is not detected. Please install Docker Desktop or Docker Engine first."
        )
        return

    defaults = {
        "ro_path": "C:\\" if platform.system() == "Windows" else "/",
        "rw_path": str(Path.home() / "llm-workspace"),
        "agent": "opencode",
    }

    # Agent
    print("\nSelect Agent:")
    print("1) Opencode (Custom)")
    print("2) Claude Code")
    print("3) Gemini CLI")
    choice = get_input("Choice", "1")
    agent_map = {"1": "opencode", "2": "claude", "3": "gemini"}
    agent_type = agent_map.get(choice, "opencode")

    # API Key
    print_step("API Key Configuration")
    api_key = get_input(f"Enter API Key for {agent_type}", hidden=True)

    # Paths
    print_step("Filesystem Access")
    ro_path = get_input("Read-Only System Path", defaults["ro_path"])
    rw_path = get_input("Read-Write Workspace Path", defaults["rw_path"])

    # Create workspace
    os.makedirs(rw_path, exist_ok=True)

    config = {
        "agent_type": agent_type,
        "api_key": api_key,
        "ro_path": os.path.abspath(ro_path),
        "rw_path": os.path.abspath(rw_path),
        "jupyter_token": "token123",  # Could be random
    }

    save_config(config)
    generate_docker_files(config)

    print_step("Building Docker images...")
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "build"], cwd=CONFIG_DIR
    )

    print_success("Setup complete! You can now run 'jupyagent start'")


def cmd_start():
    config = load_config()
    if not config:
        print_error("Configuration not found. Running setup first...")
        cmd_setup()
        config = load_config()
        if not config:
            return

    print_step("Starting Background Services...")
    try:
        subprocess.run(
            [
                "docker",
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
        )
    except subprocess.CalledProcessError:
        print_error("Failed to start services. Is Docker running?")
        return

    print_header("Environment Running")
    print(
        f"Jupyter Lab: {Colors.GREEN}http://localhost:8888{Colors.ENDC} (Token: {config.get('jupyter_token')})"
    )

    print_step("Launching Agent...")
    try:
        # Run agent interactively
        cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "run", "--rm", "agent"]
        subprocess.run(cmd, cwd=CONFIG_DIR)
    except KeyboardInterrupt:
        pass
    finally:
        print_step("Cleaning up agent container...")


def cmd_stop():
    if not COMPOSE_FILE.exists():
        print_error("Not set up.")
        return
    print_step("Stopping all services...")
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "down"], cwd=CONFIG_DIR
    )
    print_success("Stopped.")


def main():
    parser = argparse.ArgumentParser(description="JupyAgent Manager")
    parser.add_argument(
        "action",
        nargs="?",
        default="start",
        choices=["start", "setup", "stop", "config"],
        help="Action to perform",
    )

    args = parser.parse_args()

    if args.action == "setup":
        cmd_setup()
    elif args.action == "start":
        cmd_start()
    elif args.action == "stop":
        cmd_stop()
    elif args.action == "config":
        print(f"Config directory: {CONFIG_DIR}")
        if CONFIG_JSON.exists():
            with open(CONFIG_JSON, "r") as f:
                print(f.read())
        else:
            print("No config found.")


if __name__ == "__main__":
    main()
