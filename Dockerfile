FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# HF Spaces uses /data for persistent storage (mounted automatically)
RUN mkdir -p /data/chroma_db /data/obsidian_vault

ENV CHROMA_PERSIST_DIR=/data/chroma_db
ENV SQLITE_PATH=/data/kairos.db
ENV OBSIDIAN_VAULT=/data/obsidian_vault
# Local/docker-compose default (matches config.py's BACKEND_URL default and
# docker-compose.yml's port mapping + healthcheck). HF Spaces requires port
# 7860 specifically — that pinning lives only in Dockerfile.hf, swapped in
# for the hf-deploy branch, so it never affects this local/compose image.
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD sh -c "curl -f http://localhost:${PORT}/health || exit 1"

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT} --workers 1"]
