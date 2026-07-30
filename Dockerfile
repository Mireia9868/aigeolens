# AI GeoLens - Production Dockerfile
# Uses Python 3.11 slim image for small footprint and fast cold starts.

FROM python:3.11-slim

# Set working directory
WORKDIR /app/backend

# Install system dependencies (none required for now, but keep room for future)
# RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first for better Docker layer caching
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY backend/ ./

# Copy frontend static assets (Flask serves them)
COPY frontend/ /app/frontend/

# Expose port (Railway sets PORT env var at runtime)
EXPOSE 8000

# Health check — Railway will probe this
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request, os; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\", 8000)}/api/health', timeout=3)"

# Run with gunicorn — 2 workers, 120s timeout (DeepSeek API can take 30-60s)
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120", "--access-logfile", "-"]