import hashlib
import hmac


def token_digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def code_digest(secret: str, challenge_id: str, email: str, code: str) -> str:
    message = f"{challenge_id}:{email}:{code}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
