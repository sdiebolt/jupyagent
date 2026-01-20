#!/bin/bash
set -e

echo "=== JupyAgent Container Starting ==="

# Fix permissions on mounted volumes
chown -R jovyan:users /home/jovyan/.config/opencode /home/jovyan/.local/share/opencode 2>/dev/null || true
mkdir -p /home/jovyan/.local/share/opencode/log
chown -R jovyan:users /home/jovyan/.local/share/opencode

CONFIG_FILE="/home/jovyan/.config/zellij/config.kdl"

# Step 1: Generate Zellij web token (run as jovyan to access config)
echo "Generating Zellij web token..."
RAW_OUTPUT=$(su - jovyan -c "/opt/zellij/zellij --config $CONFIG_FILE web --create-token 2>&1")
echo "Zellij output: $RAW_OUTPUT"

# Extract token (format: "token_name token_value")
TOKEN=$(echo "$RAW_OUTPUT" | awk '/token_/ {print $2}')

if [ -z "$TOKEN" ]; then
    echo "CRITICAL: Token extraction failed!"
    echo "Raw output was: $RAW_OUTPUT"
    exit 1
fi

echo "Token generated: $TOKEN"

# Step 2: Export token as environment variable for supervisord
export JUPYTER_TOKEN="$TOKEN"

# Step 3: Generate opencode MCP config with the token
# Note: opencode reads MCP servers from mcp.json, not config.json
sed "s/TOKEN_PLACEHOLDER/$TOKEN/g" /home/jovyan/opencode.json.template > /home/jovyan/.config/opencode/mcp.json
chown jovyan:users /home/jovyan/.config/opencode/mcp.json
# Remove any invalid config files
rm -f /home/jovyan/.config/opencode/config.json
rm -f /home/jovyan/.config/opencode/opencode.json
echo "Opencode MCP config generated"

# Step 4: Write token to workspace for dashboard access
echo "$TOKEN" > /workspace/ZELLIJ_TOKEN.txt
chmod 644 /workspace/ZELLIJ_TOKEN.txt
chown jovyan:users /workspace/ZELLIJ_TOKEN.txt
echo "Token written to /workspace/ZELLIJ_TOKEN.txt"

# Step 5: Start supervisord with the token in environment
echo "=== Starting supervisord ==="
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
