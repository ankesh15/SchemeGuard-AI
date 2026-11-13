FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_DEFAULT_TIMEOUT=90
WORKDIR /app
RUN groupadd --gid 10001 schemeguard && useradd --uid 10001 --gid schemeguard --create-home schemeguard
COPY backend/requirements.lock ./
RUN pip install --require-hashes -r requirements.lock

FROM base AS development
COPY backend/requirements-dev.lock ./
RUN pip install --require-hashes -r requirements-dev.lock
COPY --chown=schemeguard:schemeguard backend/ ./
COPY --chown=schemeguard:schemeguard data/ ./data/
RUN mkdir -p /var/lib/schemeguard/documents && chown schemeguard:schemeguard /var/lib/schemeguard/documents && chmod 700 /var/lib/schemeguard/documents
USER schemeguard
EXPOSE 8000
ENTRYPOINT ["python", "-m", "app.bootstrap"]

FROM base AS production
COPY --chown=schemeguard:schemeguard backend/app/ ./app/
COPY --chown=schemeguard:schemeguard backend/alembic/ ./alembic/
COPY --chown=schemeguard:schemeguard backend/alembic.ini backend/logging.json ./
COPY --chown=schemeguard:schemeguard data/ ./data/
RUN mkdir -p /var/lib/schemeguard/documents && chown schemeguard:schemeguard /var/lib/schemeguard/documents && chmod 700 /var/lib/schemeguard/documents
USER schemeguard
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready',timeout=3)"
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers", "--log-config", "/app/logging.json"]
