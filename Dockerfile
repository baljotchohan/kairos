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
# HF Spaces requires port 7860
ENV PORT=7860

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
