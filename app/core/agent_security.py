import hashlib
import hmac
import secrets
from uuid import uuid4


def generate_agent_credential() -> tuple[
    str,
    str,
    str,
]:
    key_id = uuid4().hex

    secret = secrets.token_urlsafe(
        32
    )

    token = (
        f"{key_id}.{secret}"
    )

    return (
        key_id,
        secret,
        token,
    )


def hash_agent_secret(
    secret: str,
) -> str:
    return hashlib.sha256(
        secret.encode("utf-8")
    ).hexdigest()


def verify_agent_secret(
    secret: str,
    expected_hash: str,
) -> bool:
    actual_hash = (
        hash_agent_secret(secret)
    )

    return hmac.compare_digest(
        actual_hash,
        expected_hash,
    )


def parse_agent_token(
    token: str,
) -> tuple[str, str] | None:
    key_id, separator, secret = (
        token.partition(".")
    )

    if (
        not separator
        or not key_id
        or not secret
    ):
        return None

    return key_id, secret