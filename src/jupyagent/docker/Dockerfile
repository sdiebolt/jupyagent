FROM jupyter/base-notebook:latest

USER root

# Install system dependencies and dev tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    openssl \
    curl \
    supervisor \
    git \
    vim \
    nano \
    build-essential \
    jq \
    htop \
    tree \
    && rm -rf /var/lib/apt/lists/*

# Create directories with proper permissions
RUN mkdir -p /opt/zellij && chown -R ${NB_UID}:${NB_GID} /opt/zellij

# Install uv
ENV UV_INSTALL_DIR="/usr/local/bin"
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Jupyter MCP server and collaboration dependencies
# We use --system to install into the system python environment
RUN uv pip install --system \
    "jupyterlab==4.4.1" \
    "jupyter-collaboration==4.0.2" \
    "jupyter-mcp-tools>=0.1.4" \
    "ipykernel" \
    "mcp-server-jupyter"

# Swap pycrdt for datalayer_pycrdt as per jupyter-mcp-server docs
RUN uv pip uninstall --system pycrdt datalayer_pycrdt || true && \
    uv pip install --system "datalayer_pycrdt==0.12.17"

# Install ttyd (web terminal)
RUN wget "https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.x86_64" -O /usr/local/bin/ttyd && \
    chmod +x /usr/local/bin/ttyd

# Create config directories
RUN mkdir -p /home/jovyan/.config/opencode && \
    mkdir -p /home/jovyan/.local/share/opencode && \
    mkdir -p /home/jovyan/.claude && \
    chown -R ${NB_UID}:${NB_GID} /home/jovyan/.config /home/jovyan/.local /home/jovyan/.cache /home/jovyan/.claude

# Install Opencode and Claude Code as jovyan user
USER ${NB_USER}
ENV HOME=/home/jovyan
RUN curl -fsSL https://opencode.ai/install | bash && \
    /home/jovyan/.opencode/bin/opencode --version
RUN curl -fsSL https://claude.ai/install.sh | bash && \
    /home/jovyan/.local/bin/claude --version
USER root

# Copy configuration files
COPY opencode.json.template /home/jovyan/opencode.json.template
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY start.sh /usr/local/bin/start.sh
COPY register-kernel.sh /usr/local/bin/register-kernel.sh
COPY run-jupyter-mcp.sh /usr/local/bin/run-jupyter-mcp.sh

# Configure JupyterLab dark theme
RUN mkdir -p /home/jovyan/.jupyter/lab/user-settings/@jupyterlab/apputils-extension
COPY jupyter_settings.json /home/jovyan/.jupyter/lab/user-settings/@jupyterlab/apputils-extension/themes.jupyterlab-settings


# Set permissions
RUN chown ${NB_UID}:${NB_GID} /home/jovyan/opencode.json.template && \
    chmod +x /usr/local/bin/start.sh && \
    chmod +x /usr/local/bin/register-kernel.sh && \
    chmod +x /usr/local/bin/run-jupyter-mcp.sh

# Create supervisor log directory
RUN mkdir -p /var/log/supervisor && \
    chown -R ${NB_UID}:${NB_GID} /var/log/supervisor

# Fix permissions for the entire home directory
RUN chown -R ${NB_UID}:${NB_GID} /home/jovyan

# Add kernel registration alias and disable conda auto-activation (as jovyan)
USER ${NB_USER}
ENV PATH="/home/jovyan/.opencode/bin:/home/jovyan/.local/bin:${PATH}"
RUN echo '' >> ~/.bashrc && echo 'alias register-kernel="source /usr/local/bin/register-kernel.sh"' >> ~/.bashrc \
    && conda config --set auto_activate_base false

# Switch back to root for entrypoint (supervisord needs root)
USER root

EXPOSE 8888 8080 3000 1455

# 8888: Jupyter Lab
# 8080: ttyd web terminal
# 3000: Opencode UI
# 1455: Opencode OAuth callback

ENTRYPOINT ["/usr/local/bin/start.sh"]
