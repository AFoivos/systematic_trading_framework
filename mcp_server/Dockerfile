FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    MCP_REPO_ROOT=/workspace \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8765

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ripgrep \
    && rm -rf /var/lib/apt/lists/*

COPY mcp_server/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /tmp/requirements.txt

COPY mcp_server /app

RUN useradd --create-home --uid 10002 mcpuser \
    && chown -R mcpuser:mcpuser /app

USER mcpuser

EXPOSE 8765

ENTRYPOINT ["/app/scripts/start-mcp.sh"]
