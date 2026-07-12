# Force Railway rebuild - 2026-07-12-16-32
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    DJANGO_SETTINGS_MODULE=dalal_project.settings \
    USE_WEBSOCKETS=false \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/logs /app/media /app/staticfiles

# Check if settings.py was copied successfully
RUN if [ ! -f /app/dalal_project/settings.py ]; then echo "ERROR: settings.py not found"; exit 1; fi
RUN echo "Settings.py exists: $(ls -la /app/dalal_project/settings.py)"
RUN echo "Properties app exists: $(ls -la /app/properties/ 2>/dev/null || echo 'NOT FOUND')"
RUN echo "Settings.py contains properties: $(grep -c 'properties' /app/dalal_project/settings.py || echo '0')"

EXPOSE 8080

ENTRYPOINT ["./entrypoint.sh"]
