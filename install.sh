#!/bin/bash
set -e

# Configuration
REPO_URL="https://raw.githubusercontent.com/sdiebolt/jupyagent/main/jupyagent.py" # PLACEHOLDER
INSTALL_DIR="$HOME/.local/bin"
EXE_NAME="jupyagent"

echo "Installing JupyAgent Manager..."

# Ensure directory exists
mkdir -p "$INSTALL_DIR"

# Download
echo "Downloading..."
if command -v curl >/dev/null 2>&1; then
    # -f fails on HTTP errors (404, 500), -L follows redirects, -s silent
    if ! curl -f -Ls "$REPO_URL" -o "$INSTALL_DIR/$EXE_NAME"; then
        echo "Error: Failed to download from $REPO_URL (HTTP 404 or connection error)"
        exit 1
    fi
elif command -v wget >/dev/null 2>&1; then
    # wget fails on 404 by default
    if ! wget -qO "$INSTALL_DIR/$EXE_NAME" "$REPO_URL"; then
         echo "Error: Failed to download from $REPO_URL"
         exit 1
    fi
else
    echo "Error: curl or wget is required."
    exit 1
fi

# Permissions
chmod +x "$INSTALL_DIR/$EXE_NAME"

# Check PATH
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo "Warning: $INSTALL_DIR is not in your PATH."
    echo "Add the following line to your shell configuration (.bashrc, .zshrc, etc.):"
    echo "  export PATH=\"\$PATH:$INSTALL_DIR\""
fi

echo "Installation complete!"
echo "Run '$EXE_NAME' to get started."
