# syntax=docker/dockerfile:1
# ============================================================
# Safar-e-Taleem — production container
# One image that works on BOTH:
#   • Hugging Face Spaces (Docker SDK) → listens on port 7860
#   • Render / Railway / Fly.io        → they inject $PORT
# ============================================================
FROM python:3.12-slim

# Fail fast, no .pyc clutter, unbuffered logs so they show in the platform UI
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install Python dependencies first (better layer caching on rebuilds)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code (secrets/.env, local DB, and tests are excluded
# via .dockerignore so they never get baked into the image)
COPY . .

# Flask-SQLAlchemy resolves the relative sqlite:///database.db path into the
# instance folder — create it so db.create_all() at import time succeeds.
RUN mkdir -p instance

# Hugging Face Spaces expects 7860; Render/Railway override via $PORT.
EXPOSE 7860

# Single gthread worker avoids SQLite write-lock contention and prevents the
# import-time seed logic from racing across processes. Threads (not sync
# workers) are required so long-lived SSE location streams don't block API
# requests — each connected browser holds one thread until the stream cycles.
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-7860} --workers 1 --threads 8 --worker-class gthread --timeout 120"]
