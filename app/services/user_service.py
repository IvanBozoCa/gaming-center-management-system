from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from sqlalchemy import select, or_
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


class AdminCustomerNotFoundError(Exception):
    pass


class AdminCustomerWalletNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class AdminCustomerSummaryResult:
    id: UUID
    username: str
    display_name: str
    is_active: bool
    created_at: datetime
    available_seconds: int
    reserved_seconds: int


@dataclass(frozen=True)
class AdminCustomerDetailResult:
    id: UUID
    username: str
    display_name: str
    is_active: bool

    created_at: datetime
    updated_at: datetime

    available_seconds: int
    reserved_seconds: int


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


def list_admin_customers(
    db: Session,
    *,
    query: str | None = None,
    is_active: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AdminCustomerSummaryResult]:
    normalized_query = (
        query.strip()
        if query is not None
        else None
    )

    statement = (
        select(
            User,
            TimeWallet.available_seconds,
            TimeWallet.reserved_seconds,
        )
        .join(
            TimeWallet,
            TimeWallet.user_id == User.id,
        )
        .where(
            User.role == "CUSTOMER"
        )
    )

    if normalized_query:
        search_pattern = (
            f"%{normalized_query}%"
        )

        statement = statement.where(
            or_(
                User.username.ilike(
                    search_pattern
                ),
                User.display_name.ilike(
                    search_pattern
                ),
            )
        )

    if is_active is not None:
        statement = statement.where(
            User.is_active.is_(is_active)
        )

    statement = (
        statement
        .order_by(
            User.display_name.asc(),
            User.username.asc(),
            User.id.asc(),
        )
        .limit(limit)
        .offset(offset)
    )

    rows = db.execute(statement).all()

    return [
        AdminCustomerSummaryResult(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            is_active=user.is_active,
            created_at=user.created_at,
            available_seconds=(
                available_seconds
            ),
            reserved_seconds=(
                reserved_seconds
            ),
        )
        for (
            user,
            available_seconds,
            reserved_seconds,
        ) in rows
    ]
    
    
def get_admin_customer_detail(
    db: Session,
    *,
    customer_id: UUID,
) -> AdminCustomerDetailResult:
    row = db.execute(
        select(
            User,
            TimeWallet,
        )
        .outerjoin(
            TimeWallet,
            TimeWallet.user_id == User.id,
        )
        .where(
            User.id == customer_id,
            User.role == "CUSTOMER",
        )
    ).one_or_none()

    if row is None:
        raise AdminCustomerNotFoundError

    customer, wallet = row

    if wallet is None:
        raise AdminCustomerWalletNotFoundError

    return AdminCustomerDetailResult(
        id=customer.id,
        username=customer.username,
        display_name=customer.display_name,
        is_active=customer.is_active,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
        available_seconds=(
            wallet.available_seconds
        ),
        reserved_seconds=(
            wallet.reserved_seconds
        ),
    )
