#!/bin/bash
set -e

# Configuration
REPO_BASE="https://raw.githubusercontent.com/sdiebolt/jupyagent/main"
INSTALL_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.jupyagent"
EXE_NAME="jupyagent"

echo "Installing JupyAgent Manager..."

# 1. Prereqs
if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is required."
    exit 1
fi

# 2. Setup App Directory & Venv
echo "Setting up environment in $APP_DIR..."
mkdir -p "$APP_DIR"
if [ ! -d "$APP_DIR/venv" ]; then
    python3 -m venv "$APP_DIR/venv"
fi

# 3. Install Dependencies
echo "Installing dependencies (textual)..."
"$APP_DIR/venv/bin/pip" install -q textual requests

# 4. Download Script
echo "Downloading application..."
if command -v curl >/dev/null 2>&1; then
    if ! curl -f -Ls "$REPO_BASE/jupyagent.py" -o "$APP_DIR/jupyagent.py"; then
        echo "Error: Failed to download application."
        exit 1
    fi
elif command -v wget >/dev/null 2>&1; then
    if ! wget -qO "$APP_DIR/jupyagent.py" "$REPO_BASE/jupyagent.py"; then
         echo "Error: Failed to download application."
         exit 1
    fi
else
    echo "Error: curl or wget is required."
    exit 1
fi

# 5. Create Wrapper
echo "Creating launcher..."
mkdir -p "$INSTALL_DIR"
cat > "$INSTALL_DIR/$EXE_NAME" <<EOF
#!/bin/bash
exec "$APP_DIR/venv/bin/python" "$APP_DIR/jupyagent.py" "\$@"
EOF
chmod +x "$INSTALL_DIR/$EXE_NAME"

# 6. Check PATH
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo "Warning: $INSTALL_DIR is not in your PATH."
    echo "Add the following line to your shell configuration (.bashrc, .zshrc, etc.):"
    echo "  export PATH=\"\$PATH:$INSTALL_DIR\""
fi

echo "Installation complete!"
echo "Run '$EXE_NAME' to get started."
