#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
docker compose exec -T api python -m tests.run "$@"

