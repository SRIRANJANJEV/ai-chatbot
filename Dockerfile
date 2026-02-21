# ──────────────────────────────────────────────────────────────────────────────
# Dockerfile — Medical Chatbot (production)
# ──────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python deps (cached layer unless requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app/          ./app/
COPY scripts/      ./scripts/
COPY templates/    ./templates/
COPY static/       ./static/
COPY run.py        ./

# Create necessary directories and set permissions
RUN mkdir -p logs data/pdfs data/vector_store \
    && chown -R appuser:appuser /app

USER appuser

# Expose Flask port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" \
  || exit 1

# ── Production server: gunicorn with 2 workers ────────────────────────────────
# For CPU-bound workloads bump workers = (2 × CPU_cores) + 1
CMD ["gunicorn", \
     "--bind",    "0.0.0.0:5000", \
     "--workers", "2", \
     "--threads", "4", \
     "--timeout", "120", \
     "--log-level", "info", \
     "--access-logfile", "logs/access.log", \
     "--error-logfile",  "logs/error.log", \
     "run:app"]
