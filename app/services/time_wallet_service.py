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
class TimePurchaseResult:
    transaction_id: UUID
    customer_id: UUID
    credited_seconds: int
    available_seconds: int
    reserved_seconds: int
    transaction_type: str
    created_at: datetime


def register_time_purchase(
    db: Session,
    *,
    customer_id: UUID,
    seconds: int,
    actor_user_id: UUID,
) -> TimePurchaseResult:
    if seconds <= 0:
        raise InvalidTimeAmountError

    try:
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
                TimeWallet.user_id
                == customer.id
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

        result = TimePurchaseResult(
            transaction_id=transaction.id,
            customer_id=customer.id,
            credited_seconds=seconds,
            available_seconds=wallet.available_seconds,
            reserved_seconds=wallet.reserved_seconds,
            transaction_type=transaction.transaction_type,
            created_at=transaction.created_at,
        )

        db.commit()

        return result

    except Exception:
        db.rollback()
        raise