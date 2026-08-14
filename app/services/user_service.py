from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.time_wallet import TimeWallet
from app.models.user import User
from app.schemas.user import UserRegister


class UsernameAlreadyExistsError(Exception):
    pass


class RegistrationConflictError(Exception):
    pass


def create_customer(
    db: Session,
    data: UserRegister,
) -> User:

    existing_user = db.scalar(
        select(User).where(User.username == data.username)
    )

    if existing_user is not None:
        raise UsernameAlreadyExistsError

    user = User(
        username=data.username,
        display_name=data.display_name,
        password_hash=hash_password(data.password),
        role="CUSTOMER",
        is_active=True,
    )

    wallet = TimeWallet(
        user=user,
        available_seconds=0,
        reserved_seconds=0,
    )

    db.add_all([user, wallet])

    try:
        db.commit()

    except IntegrityError as exc:
        db.rollback()
        raise RegistrationConflictError from exc

    except Exception:
        db.rollback()
        raise

    db.refresh(user)

    return user