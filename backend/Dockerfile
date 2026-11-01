FROM python:3.11-slim

# psycopg[binary] ships its own libpq, so no Postgres dev headers are
# needed here. lxml (document/website ingestion) needs these.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        pkg-config \
        libxml2-dev \
        libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

ENV DJANGO_SETTINGS_MODULE=config.settings.prod \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# daphne serves the ASGI app (HTTP + WebSocket) — same application object
# used for both in config/asgi.py. Static files are collected in the
# image build step by the deploy pipeline (`collectstatic`), not at
# container startup, so a slow/failing static build never blocks the web
# process coming up.
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
