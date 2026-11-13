"""Validate production Compose structure without printing expanded environment secrets."""

import argparse
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--env-file", type=Path, default=Path(".env.production"))
args = parser.parse_args()
result = subprocess.check_output(
    [
        "docker",
        "compose",
        "--env-file",
        str(args.env_file),
        "-f",
        "docker-compose.production.yml",
        "config",
        "--format",
        "json",
    ]
)
services = json.loads(result)["services"]
assert set(services) == {"db", "redis", "frontend", "api", "worker", "scheduler"}
for name in ("db", "redis"):
    assert not services[name].get("ports")
for name in ("api", "frontend", "worker", "scheduler"):
    service = services[name]
    assert service["read_only"] and service["restart"] == "unless-stopped"
    assert all(item.startswith("/") for item in service.get("tmpfs", []))
    if name in {"worker", "scheduler"}:
        assert service["healthcheck"]["test"]
    else:
        assert (
            "HEALTHCHECK"
            in Path("backend/Dockerfile" if name == "api" else "frontend/Dockerfile").read_text()
        )
assert "--queues=monitoring,documents" in services["worker"]["command"]
assert services["api"]["environment"]["POSTGRES_USER"] != services["db"]["environment"]["POSTGRES_USER"]
assert services["api"]["environment"]["APP_ENV"] == "production"
assert not any(
    key in services["frontend"]["environment"]
    for key in ("GEMINI_API_KEY", "POSTGRES_PASSWORD", "PROFILE_ENCRYPTION_KEY")
)
print(
    "PASS: six-service production manifest, private data ports, bounded writable mounts, exact worker queues, separate DB roles and frontend secret boundary"
)
