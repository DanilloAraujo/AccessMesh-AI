# syntax=docker/dockerfile:1
# ──────────────────────────────────────────────────────────────────────────
# AccessMesh-AI — Backend (FastAPI + Uvicorn)
# Build context MUST be the repository root (packages shared/, services/,
# agents/ and mcp/ are imported by this service):
#   docker build -f backend/Dockerfile -t accessmesh-backend .
# ──────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Azure Cognitive Services Speech SDK requires native audio/SSL libraries.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libssl-dev \
        libasound2 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer caching — only rebuilds on requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only the packages used by the backend
COPY shared/    ./shared/
COPY services/  ./services/
COPY agents/    ./agents/
COPY mcp/       ./mcp/
COPY backend/   ./backend/

# Expose the port expected by Azure Container Apps (default ingress port)
EXPOSE 8000

# Single worker: Container Apps scales horizontally via replicas.
CMD ["uvicorn", "backend.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1"]
