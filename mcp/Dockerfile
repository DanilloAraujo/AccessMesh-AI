# syntax=docker/dockerfile:1
# ──────────────────────────────────────────────────────────────────────────
# AccessMesh-AI — MCP Server (FastAPI + Uvicorn)
# Build context MUST be the repository root:
#   docker build -f mcp/Dockerfile -t accessmesh-mcp .
# ──────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Azure Cognitive Services Speech SDK requires native audio/SSL libraries.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libssl-dev \
        libasound2 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# MCP server only needs shared, services, and mcp packages
COPY shared/    ./shared/
COPY services/  ./services/
COPY mcp/       ./mcp/

EXPOSE 8000

CMD ["uvicorn", "mcp.mcp_server:mcp_app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1"]
