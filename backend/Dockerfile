FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN groupadd --gid 10001 schemeguard && useradd --uid 10001 --gid schemeguard --create-home schemeguard
COPY backend/requirements.lock ./
RUN pip install --require-hashes -r requirements.lock

FROM base AS development
COPY backend/requirements-dev.lock ./
RUN pip install --require-hashes -r requirements-dev.lock
COPY --chown=schemeguard:schemeguard backend/ ./
COPY --chown=schemeguard:schemeguard data/ ./data/
USER schemeguard
EXPOSE 8000
ENTRYPOINT ["python", "-m", "app.bootstrap"]
