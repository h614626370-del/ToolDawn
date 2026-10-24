"""Run from services/api with uv; never print connection credentials."""

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values


def main() -> None:
    api_root = Path(__file__).resolve().parents[1] / "services" / "api"
    values = dotenv_values(api_root / ".env")
    test_url = values.get("TOOLDAWN_TEST_DATABASE_URL")
    redis_url = values.get("TOOLDAWN_REDIS_URL")
    if not test_url or urlsplit(test_url).path != "/tooldawn_test":
        raise SystemExit("Configure the dedicated tooldawn_test database first.")
    if not redis_url:
        raise SystemExit("Configure the remote Redis connection first.")
    env = dict(os.environ)
    env.update(
        TOOLDAWN_DATABASE_URL=test_url,
        TOOLDAWN_TEST_DATABASE_URL=test_url,
        TOOLDAWN_TEST_REDIS_URL=redis_url,
    )
    for command in (
        ["alembic", "upgrade", "head"],
        ["tooldawn.cli", "seed-catalog"],
        ["tooldawn.cli", "install-text-tools"],
        ["pytest", "-q", *sys.argv[1:]],
    ):
        subprocess.run(
            [sys.executable, "-m", *command],
            cwd=api_root,
            env=env,
            check=True,
        )


if __name__ == "__main__":
    main()
