#!/bin/bash
# register-kernel.sh - Register a virtual environment as a Jupyter kernel
# This script is meant to be sourced, so we use return instead of exit

if [ -z "$VIRTUAL_ENV" ]; then
    echo "Error: You must be inside a virtual environment." >&2
    return 1 2>/dev/null || true
fi

VENV_PYTHON="${VIRTUAL_ENV}/bin/python"
VENV_NAME=$(basename "$VIRTUAL_ENV")
echo "Found venv: ${VENV_NAME}"

# Use uv pip if available, otherwise fallback to pip
if command -v uv &> /dev/null; then
    PIP_CMD="uv pip"
else
    PIP_CMD="$VENV_PYTHON -m pip"
fi

if ! "$VENV_PYTHON" -m pip show ipykernel &> /dev/null; then
    echo "Installing ipykernel..."
    $PIP_CMD install ipykernel || { echo "Failed to install ipykernel" >&2; return 1 2>/dev/null || true; }
fi

echo "Registering kernel..."
"$VENV_PYTHON" -m ipykernel install --user --name "${VENV_NAME}" --display-name "Python (${VENV_NAME})" || { echo "Failed to register kernel" >&2; return 1 2>/dev/null || true; }
echo "Kernel '${VENV_NAME}' registered."
