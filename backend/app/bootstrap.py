"""Single development API process: migrate before accepting requests."""

import os
import subprocess
import sys


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("A server command is required")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
