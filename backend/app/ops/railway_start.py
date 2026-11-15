"""Apply safe, repeatable Railway release steps, then drop owner credentials.

Railway runs a service's pre-deploy command with the service's runtime
environment. This entry point runs migrations, insert-only catalog seeding,
and the existing least-privilege grants as short-lived child processes. The
long-running API process receives only the restricted runtime database URL.
"""

from __future__ import annotations

import os
import subprocess
import sys


OWNER_ONLY_VARIABLES = {
    "MIGRATION_DATABASE_URL",
    "RUNTIME_DATABASE_URL",
    "RUNTIME_DATABASE_USER",
    "RUNTIME_DATABASE_PASSWORD",
}


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Railway release configuration is missing {name}")
    return value


def _run(command: list[str], environment: dict[str, str]) -> None:
    subprocess.run(command, check=True, env=environment, cwd="/app")


def main() -> None:
    migration_url = _required("MIGRATION_DATABASE_URL")
    runtime_url = _required("RUNTIME_DATABASE_URL")
    runtime_user = _required("RUNTIME_DATABASE_USER")
    runtime_password = _required("RUNTIME_DATABASE_PASSWORD")

    owner_environment = os.environ.copy()
    owner_environment["DATABASE_URL"] = migration_url
    owner_environment.pop("MIGRATION_DATABASE_URL", None)
    owner_environment.pop("RUNTIME_DATABASE_URL", None)
    owner_environment.pop("RUNTIME_DATABASE_USER", None)
    owner_environment.pop("RUNTIME_DATABASE_PASSWORD", None)

    _run(["alembic", "upgrade", "head"], owner_environment)
    _run([sys.executable, "-m", "app.seed"], owner_environment)

    grant_environment = owner_environment | {
        "RUNTIME_DATABASE_USER": runtime_user,
        "RUNTIME_DATABASE_PASSWORD": runtime_password,
    }
    _run([sys.executable, "-m", "app.ops.grant_runtime"], grant_environment)

    port = os.environ.get("PORT", "8000")
    if not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise SystemExit("Railway PORT must be a valid TCP port")

    runtime_environment = os.environ.copy()
    runtime_environment["DATABASE_URL"] = runtime_url
    for name in OWNER_ONLY_VARIABLES:
        runtime_environment.pop(name, None)

    os.execvpe(
        "uvicorn",
        [
            "uvicorn",
            "app.main:create_app",
            "--factory",
            "--host",
            "0.0.0.0",
            "--port",
            port,
            "--no-access-log",
            "--no-proxy-headers",
            "--log-config",
            "/app/logging.json",
        ],
        runtime_environment,
    )


if __name__ == "__main__":
    main()
