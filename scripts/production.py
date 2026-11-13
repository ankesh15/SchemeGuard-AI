"""Local operator release commands; never deploys or creates cloud resources."""

import argparse
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def environment(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not key.replace("_", "").isalnum():
            raise ValueError("Unsupported environment file entry")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        result[key] = value
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["migrate", "grant-runtime", "check"])
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env.production")
    args = parser.parse_args()
    args.env_file = args.env_file.resolve()
    values = environment(args.env_file)
    command = ["docker", "compose", "--env-file", str(args.env_file), "-f", "docker-compose.production.yml"]
    if args.action == "check":
        subprocess.run(command + ["config", "--quiet"], cwd=ROOT, check=True)
        return
    runenv = os.environ | values
    runenv["RUNTIME_DATABASE_USER"] = values["POSTGRES_USER"]
    runenv["RUNTIME_DATABASE_PASSWORD"] = values["POSTGRES_PASSWORD"]
    runenv["POSTGRES_USER"] = values["POSTGRES_OWNER"]
    runenv["POSTGRES_PASSWORD"] = values["POSTGRES_OWNER_PASSWORD"]
    runenv["DATABASE_URL"] = values.get("MIGRATION_DATABASE_URL", "")
    extras = []
    for key in (
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "DATABASE_URL",
        "RUNTIME_DATABASE_USER",
        "RUNTIME_DATABASE_PASSWORD",
    ):
        extras += ["-e", key]
    target = (
        ["alembic", "upgrade", "head"]
        if args.action == "migrate"
        else ["python", "-m", "app.ops.grant_runtime"]
    )
    subprocess.run(
        command + ["run", "--rm", "--no-deps", "-T", *extras, "api", *target],
        cwd=ROOT,
        env=runenv,
        check=True,
    )


if __name__ == "__main__":
    main()
