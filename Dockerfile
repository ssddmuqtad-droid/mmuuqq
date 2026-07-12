# Force complete rebuild: 2026-07-12T16:22:00Z - Include all Django app code
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

# Copy configuration files first (most stable layer)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy all application code and configuration
COPY manage.py /app/
COPY run_server.py /app/
COPY entrypoint.sh /app/
COPY nixpacks.toml /app/
COPY railway.toml /app/
COPY railway.json /app/

# Copy Django project and apps - CRITICAL FOR RUNTIME
COPY dalal_project /app/dalal_project/
COPY properties /app/properties/
COPY templates /app/templates/

# Verify files were copied
RUN ls -la /app/dalal_project/
RUN test -f /app/dalal_project/settings.py || (echo "ERROR: settings.py not found!" && exit 1)
RUN test -f /app/dalal_project/__init__.py || (echo "ERROR: dalal_project/__init__.py not found!" && exit 1)

# Create necessary directories for runtime
RUN mkdir -p /app/logs /app/media /app/staticfiles /app/static /app/locale

# Make entrypoint executable
RUN chmod +x /app/entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["./entrypoint.sh"]
