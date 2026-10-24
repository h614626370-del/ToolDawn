"""Run on the designated Linux server; never prints credentials."""

import hashlib
import os
import secrets
import subprocess
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent
    if os.name != "posix" or str(root) != "/opt/tooldawn-infra":
        raise SystemExit("Run only from /opt/tooldawn-infra on the designated server.")
    root.chmod(0o700)
    secret_dir = root / "secrets"
    secret_dir.mkdir(mode=0o700, exist_ok=True)
    secret_dir.chmod(0o700)
    for name in (
        "postgres_admin_password",
        "postgres_app_password",
        "postgres_test_password",
        "redis_password",
    ):
        target = secret_dir / name
        if not target.exists():
            with target.open("x", encoding="utf-8") as stream:
                stream.write(secrets.token_hex(32))
        # Compose mounts these as files; service users must read them.
        # The host parent directory is root-only.
        target.chmod(0o444)
    password = (secret_dir / "redis_password").read_text(encoding="utf-8").strip()
    digest = hashlib.sha256(password.encode()).hexdigest()
    acl = secret_dir / "redis.acl"
    acl.write_text(
        f"user default off\n"
        f"user tooldawn on #{digest} ~tooldawn:* &tooldawn:* "
        "+@connection +@read +@write +@scripting +@transaction -@dangerous\n",
        encoding="utf-8",
    )
    acl.chmod(0o444)
    subprocess.run(
        ["docker", "compose", "up", "-d", "--wait", "--wait-timeout", "120"],
        cwd=root,
        check=True,
    )
    print("ToolDawn infrastructure is healthy. Credentials remain in the root-only secret directory.")


if __name__ == "__main__":
    main()
