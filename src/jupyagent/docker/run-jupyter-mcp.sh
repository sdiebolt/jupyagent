#!/bin/bash
set -e

LOGfile="/tmp/mcp-debug.log"
echo "=== Starting run-jupyter-mcp.sh at $(date) ===" > "$LOGfile"
echo "Arguments: $@" >> "$LOGfile"
echo "PATH: $PATH" >> "$LOGfile"
echo "User: $(whoami)" >> "$LOGfile"

# Extract URL from environment or default
URL="${JUPYTER_URL:-http://localhost:8888}"

echo "Target URL: $URL" >> "$LOGfile"

# Wait for Jupyter to be ready
echo "Waiting for Jupyter at $URL..." >> "$LOGfile"
for i in {1..60}; do
    if curl -s "$URL/api" > /dev/null; then
        echo "Jupyter is up!" >> "$LOGfile"
        break
    fi
    echo "Retry $i..." >> "$LOGfile"
    sleep 1
done

# Find the executable
MCP_BIN=$(which mcp-server-jupyter || echo "NOT_FOUND")
echo "mcp-server-jupyter location: $MCP_BIN" >> "$LOGfile"

if [ "$MCP_BIN" = "NOT_FOUND" ]; then
    echo "ERROR: mcp-server-jupyter not found in PATH" >> "$LOGfile"
    exit 1
fi

# Launch the actual MCP server
# We explicitly pass 'stdio' as the transport argument, which is expected by the server
echo "Execing: $MCP_BIN stdio" >> "$LOGfile"
exec "$MCP_BIN" stdio
