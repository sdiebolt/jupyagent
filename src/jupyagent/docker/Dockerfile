FROM jupyter/base-notebook:latest

USER root

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    openssl \
    curl \
    supervisor \
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

# Install Zellij
RUN wget "https://github.com/zellij-org/zellij/releases/latest/download/zellij-x86_64-unknown-linux-musl.tar.gz" -O /tmp/zellij.tar.gz && \
    tar -C /opt/zellij -xvf /tmp/zellij.tar.gz && rm /tmp/zellij.tar.gz

# Create all config directories first (needed before opencode install)
RUN mkdir -p /home/jovyan/.config/zellij/certs && \
    mkdir -p /home/jovyan/.local/share/zellij && \
    mkdir -p /home/jovyan/.cache/zellij && \
    mkdir -p /home/jovyan/.config/opencode && \
    mkdir -p /home/jovyan/.local/share/opencode && \
    chown -R ${NB_UID}:${NB_GID} /home/jovyan/.config /home/jovyan/.local /home/jovyan/.cache

# Generate self-signed certs for Zellij
RUN openssl req -x509 -newkey rsa:4096 \
    -keyout /home/jovyan/.config/zellij/certs/key.pem \
    -out /home/jovyan/.config/zellij/certs/cert.pem \
    -days 365 -nodes -subj '/CN=localhost' && \
    chown ${NB_UID}:${NB_GID} /home/jovyan/.config/zellij/certs/*.pem

# Install Opencode as jovyan user
USER ${NB_USER}
ENV HOME=/home/jovyan
RUN curl -fsSL https://opencode.ai/install | bash && \
    /home/jovyan/.opencode/bin/opencode --version
USER root

# Copy configuration files
COPY zellij-config.kdl /home/jovyan/.config/zellij/config.kdl
COPY opencode.json.template /home/jovyan/opencode.json.template
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY start.sh /usr/local/bin/start.sh
COPY register-kernel.sh /usr/local/bin/register-kernel.sh
COPY run-jupyter-mcp.sh /usr/local/bin/run-jupyter-mcp.sh

# Configure JupyterLab dark theme
RUN mkdir -p /home/jovyan/.jupyter/lab/user-settings/@jupyterlab/apputils-extension
COPY jupyter_settings.json /home/jovyan/.jupyter/lab/user-settings/@jupyterlab/apputils-extension/themes.jupyterlab-settings


# Set permissions
RUN chown ${NB_UID}:${NB_GID} /home/jovyan/.config/zellij/config.kdl && \
    chown ${NB_UID}:${NB_GID} /home/jovyan/opencode.json.template && \
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
ENV PATH="/opt/zellij:/home/jovyan/.opencode/bin:${PATH}"
RUN echo '' >> ~/.bashrc && echo 'alias register-kernel="source /usr/local/bin/register-kernel.sh"' >> ~/.bashrc \
    && conda config --set auto_activate_base false

# Switch back to root for entrypoint (supervisord needs root)
USER root

EXPOSE 8888 8080 3000

ENTRYPOINT ["/usr/local/bin/start.sh"]
