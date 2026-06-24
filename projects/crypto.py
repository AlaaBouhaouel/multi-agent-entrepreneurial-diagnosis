import base64
import hashlib
import os
from functools import lru_cache

from cryptography.fernet import Fernet
from django.conf import settings


_ENC_PREFIX = "enc:v1:"


def _derive_fernet_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    # Recommended: set FIELD_ENCRYPTION_KEY in env/secret manager.
    env_key = (os.getenv("FIELD_ENCRYPTION_KEY") or "").strip()
    if env_key:
        # If not already a valid Fernet key, derive a deterministic one from it.
        try:
            key_bytes = env_key.encode("utf-8")
            Fernet(key_bytes)
            return Fernet(key_bytes)
        except Exception:
            return Fernet(_derive_fernet_key(env_key))

    # Fallback to Django SECRET_KEY for backward compatibility.
    return Fernet(_derive_fernet_key(settings.SECRET_KEY))


def encrypt_text(value: str) -> str:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    if value.startswith(_ENC_PREFIX):
        return value
    token = _get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{_ENC_PREFIX}{token}"


def decrypt_text(value: str) -> str:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    if not value.startswith(_ENC_PREFIX):
        return value
    token = value[len(_ENC_PREFIX):]
    return _get_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
