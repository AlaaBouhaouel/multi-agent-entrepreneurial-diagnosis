from __future__ import annotations

import base64
import hashlib
import os
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet


def llm_pii_mode() -> str:
    """
    Controls how sensitive identity fields are shown to the LLM.
    Allowed values: "encrypted", "plain"
    Default: encrypted
    """
    mode = (os.getenv("LLM_PII_MODE") or "encrypted").strip().lower()
    return "plain" if mode == "plain" else "encrypted"


def _resolve_secret() -> str:
    # Preferred key for field privacy in prompts.
    secret = (os.getenv("FIELD_ENCRYPTION_KEY") or "").strip()
    if secret:
        return secret

    # Reuse Django SECRET_KEY when available.
    try:
        from django.conf import settings
        django_secret = getattr(settings, "SECRET_KEY", "")
        if django_secret:
            return str(django_secret)
    except Exception:
        pass

    # Dev fallback to avoid crashes in standalone scripts.
    return "leadit-dev-change-me"


def _derive_fernet_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    secret = _resolve_secret()
    try:
        raw = secret.encode("utf-8")
        Fernet(raw)
        return Fernet(raw)
    except Exception:
        return Fernet(_derive_fernet_key(secret))


def pii_for_llm(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if llm_pii_mode() == "plain":
        return text
    return "enc:v1:" + _fernet().encrypt(text.encode("utf-8")).decode("utf-8")
