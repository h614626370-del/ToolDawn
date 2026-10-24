import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException


class SecretBox:
    def __init__(self, settings):
        secret = settings.encryption_key or settings.auth_secret
        self.cipher = None
        if secret:
            key = hashlib.sha256(
                b"tooldawn-settings-v1:" + secret.get_secret_value().encode()
            ).digest()
            self.cipher = Fernet(base64.urlsafe_b64encode(key))

    def encrypt(self, value: str) -> str:
        if not self.cipher:
            raise HTTPException(503, "配置加密密钥尚未就绪。")
        return self.cipher.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        try:
            if not self.cipher:
                raise InvalidToken()
            return self.cipher.decrypt(value.encode()).decode()
        except (InvalidToken, ValueError):
            raise HTTPException(503, "配置密钥无法解密，请检查服务器加密根密钥。") from None
