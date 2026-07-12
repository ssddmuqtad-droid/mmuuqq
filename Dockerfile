# Force Railway rebuild - 2026-07-12-18-27 - Fix locale copy issue
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

# Explicitly copy all important directories (make them conditional if they don't exist)
COPY dalal_project /app/dalal_project/

# Copy properties directory if it exists, otherwise create it
RUN if [ -d properties ]; then cp -r properties /app/properties/; else mkdir -p /app/properties; fi

COPY manage.py /app/
COPY run_server.py /app/
COPY entrypoint.sh /app/
COPY nixpacks.toml /app/
COPY railway.toml /app/
COPY railway.json /app/

# Copy templates directory if it exists, otherwise create it
RUN if [ -d templates ]; then cp -r templates /app/templates/; else mkdir -p /app/templates; fi

# Copy static directory if it exists
RUN if [ -d static ]; then cp -r static /app/static/; else mkdir -p /app/static; fi

# Copy locale directory if it exists
RUN if [ -d locale ]; then cp -r locale /app/locale/; else mkdir -p /app/locale; fi

RUN mkdir -p /app/logs /app/media /app/staticfiles

# Check if settings.py was copied successfully
RUN if [ ! -f /app/dalal_project/settings.py ]; then echo "ERROR: settings.py not found"; exit 1; fi
RUN echo "Settings.py exists: $(ls -la /app/dalal_project/settings.py)"
RUN echo "Properties app exists: $(ls -la /app/properties/ 2>/dev/null || echo 'NOT FOUND')"
RUN echo "Settings.py contains properties: $(grep -c 'properties' /app/dalal_project/settings.py || echo '0')"

EXPOSE 8080

ENTRYPOINT ["./entrypoint.sh"]
