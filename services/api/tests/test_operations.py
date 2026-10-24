import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from tooldawn.config import Settings
from tooldawn.modules.auth.passwords import hash_password, verify_password
from tooldawn.modules.operations.schemas import AccountInput, RuntimeConfig
from tooldawn.modules.operations.secrets import SecretBox


def test_password_hash_is_salted_and_verified():
    password = "temporary-test-password"
    encoded = hash_password(password)
    assert encoded != hash_password(password)
    assert password not in encoded
    assert verify_password(password, encoded)
    assert not verify_password("incorrect-password", encoded)
    assert not verify_password(password, "malformed")


def test_secrets_are_encrypted_and_wrong_key_is_generic():
    box = SecretBox(Settings(_env_file=None, auth_secret="unit-test-secret-" * 4))
    encrypted = box.encrypt("private-api-key")
    assert "private-api-key" not in encrypted
    assert box.decrypt(encrypted) == "private-api-key"
    other = SecretBox(Settings(_env_file=None, auth_secret="another-test-secret-" * 4))
    with pytest.raises(HTTPException) as exc:
        other.decrypt(encrypted)
    assert exc.value.status_code == 503
    assert encrypted not in exc.value.detail


@pytest.mark.parametrize(
    "url",
    [
        "https://user:secret@example.com/v1",
        "http://example.com/v1",
        "https://example.com/v1?key=secret",
        "https://example.com/#fragment",
    ],
)
def test_model_url_rejects_insecure_or_embedded_credentials(url):
    with pytest.raises(ValidationError):
        AccountInput(name="Test", base_url=url, model="test")


def test_business_settings_validate_email_and_unique_packages():
    with pytest.raises(ValidationError):
        RuntimeConfig(contact_email="invalid")
    with pytest.raises(ValidationError):
        RuntimeConfig(
            credit_packages=[
                {"id": "same", "credits": 100, "unit_amount": 500},
                {"id": "same", "credits": 200, "unit_amount": 600},
            ]
        )
