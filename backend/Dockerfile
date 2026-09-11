# SatQuery AI backend (PRD §19) — CPU base; see docker-compose.yml for GPU notes.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    SATQUERY_DATA_DIR=/data

# GDAL ships inside the rasterio manylinux wheels; no system GDAL needed.
WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend /app/backend

# models/ and datasets/ are mounted volumes (never baked in, §7.5).
VOLUME ["/data"]
ENV PYTHONPATH=/app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/api/v1/health', timeout=4)" || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
