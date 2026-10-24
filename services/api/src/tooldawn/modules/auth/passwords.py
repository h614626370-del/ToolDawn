import hashlib
import hmac
import secrets


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=2**17, r=8, p=1, maxmem=256 * 1024 * 1024, dklen=32
    )
    return f"scrypt-v1${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        hash_password(password)
        return False
    try:
        version, salt, digest = encoded.split("$")
        if version != "scrypt-v1":
            return False
        actual = hashlib.scrypt(
            password.encode(),
            salt=bytes.fromhex(salt),
            n=2**17,
            r=8,
            p=1,
            maxmem=256 * 1024 * 1024,
            dklen=32,
        )
        return hmac.compare_digest(actual.hex(), digest)
    except (ValueError, TypeError):
        return False
