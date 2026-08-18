from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.time_transaction import TimeTransaction
from app.models.time_wallet import TimeWallet
from app.models.user import User


class InvalidTimeAmountError(Exception):
    pass


class CustomerNotFoundError(Exception):
    pass


class InactiveCustomerError(Exception):
    pass


class CustomerWalletNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class AdminCustomerWalletResult:
    available_seconds: int
    reserved_seconds: int


@dataclass(frozen=True)
class AdminTimeTransactionResult:
    id: UUID
    transaction_type: str
    available_seconds_delta: int
    reserved_seconds_delta: int
    actor_user_id: UUID | None
    created_at: datetime


@dataclass(frozen=True)
class TimePurchaseResult:
    transaction_id: UUID
    customer_id: UUID
    credited_seconds: int
    available_seconds: int
    reserved_seconds: int
    transaction_type: str
    created_at: datetime


def apply_time_purchase(
    db: Session,
    *,
    customer_id: UUID,
    seconds: int,
    actor_user_id: UUID,
) -> TimePurchaseResult:
    """
    Aplica una compra de tiempo sin hacer commit.

    El caller es responsable de confirmar o revertir
    la transacción.
    """
    if seconds <= 0:
        raise InvalidTimeAmountError

    customer = db.scalar(
        select(User)
        .where(
            User.id == customer_id
        )
        .with_for_update()
    )

    if (
        customer is None
        or customer.role != "CUSTOMER"
    ):
        raise CustomerNotFoundError

    if not customer.is_active:
        raise InactiveCustomerError

    wallet = db.scalar(
        select(TimeWallet)
        .where(
            TimeWallet.user_id == customer.id
        )
        .with_for_update()
    )

    if wallet is None:
        raise CustomerWalletNotFoundError

    wallet.available_seconds += seconds

    transaction = TimeTransaction(
        wallet_id=wallet.id,
        transaction_type="PURCHASE",
        available_seconds_delta=seconds,
        reserved_seconds_delta=0,
        actor_user_id=actor_user_id,
    )

    db.add(transaction)

    db.flush()
    db.refresh(transaction)

    return TimePurchaseResult(
        transaction_id=transaction.id,
        customer_id=customer.id,
        credited_seconds=seconds,
        available_seconds=wallet.available_seconds,
        reserved_seconds=wallet.reserved_seconds,
        transaction_type=transaction.transaction_type,
        created_at=transaction.created_at,
    )


def register_time_purchase(
    db: Session,
    *,
    customer_id: UUID,
    seconds: int,
    actor_user_id: UUID,
) -> TimePurchaseResult:
    try:
        result = apply_time_purchase(
            db,
            customer_id=customer_id,
            seconds=seconds,
            actor_user_id=actor_user_id,
        )

        db.commit()

        return result

    except Exception:
        db.rollback()
        raise
       

def _get_customer_wallet_for_read(
    db: Session,
    *,
    customer_id: UUID,
) -> TimeWallet:
    customer = db.scalar(
        select(User).where(
            User.id == customer_id
        )
    )

    if (
        customer is None
        or customer.role != "CUSTOMER"
    ):
        raise CustomerNotFoundError

    wallet = db.scalar(
        select(TimeWallet).where(
            TimeWallet.user_id
            == customer.id
        )
    )

    if wallet is None:
        raise CustomerWalletNotFoundError

    return wallet


def get_admin_customer_wallet(
    db: Session,
    *,
    customer_id: UUID,
) -> AdminCustomerWalletResult:
    wallet = _get_customer_wallet_for_read(
        db,
        customer_id=customer_id,
    )

    return AdminCustomerWalletResult(
        available_seconds=(
            wallet.available_seconds
        ),
        reserved_seconds=(
            wallet.reserved_seconds
        ),
    )


def list_admin_customer_time_transactions(
    db: Session,
    *,
    customer_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[AdminTimeTransactionResult]:
    wallet = _get_customer_wallet_for_read(
        db,
        customer_id=customer_id,
    )

    transactions = db.scalars(
        select(TimeTransaction)
        .where(
            TimeTransaction.wallet_id
            == wallet.id
        )
        .order_by(
            TimeTransaction.created_at.desc(),
            TimeTransaction.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    ).all()

    return [
        AdminTimeTransactionResult(
            id=transaction.id,
            transaction_type=(
                transaction.transaction_type
            ),
            available_seconds_delta=(
                transaction.available_seconds_delta
            ),
            reserved_seconds_delta=(
                transaction.reserved_seconds_delta
            ),
            actor_user_id=(
                transaction.actor_user_id
            ),
            created_at=(
                transaction.created_at
            ),
        )
        for transaction in transactions
    ]