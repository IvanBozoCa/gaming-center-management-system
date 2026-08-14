from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    DUMMY_PASSWORD_HASH,
    verify_password,
)
from app.models.user import User


class InvalidCredentialsError(Exception):
    pass


def authenticate_user(
    db: Session,
    username: str,
    password: str,
) -> User:

    normalized_username = username.strip().lower()

    if not normalized_username or not password:
        verify_password(
            password,
            DUMMY_PASSWORD_HASH,
        )

        raise InvalidCredentialsError

    user = db.scalar(
        select(User).where(
            User.username == normalized_username
        )
    )

    if user is None:
        verify_password(
            password,
            DUMMY_PASSWORD_HASH,
        )

        raise InvalidCredentialsError

    if not verify_password(
        password,
        user.password_hash,
    ):
        raise InvalidCredentialsError

    if not user.is_active:
        raise InvalidCredentialsError

    return user