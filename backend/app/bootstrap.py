"""Single development API process: migrate before accepting requests."""

import os
import subprocess
import sys

from app.core.config import get_settings


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("A server command is required")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    if get_settings().seed_demo_data:
        subprocess.run([sys.executable, "-m", "app.seed"], check=True)
        subprocess.run([sys.executable, "-m", "app.seed_demo"], check=True)
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
