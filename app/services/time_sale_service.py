from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.time_product import TimeProduct
from app.models.time_sale import TimeSale
from app.services.time_product_service import (
    TimeProductNotFoundError,
)
from app.services.time_wallet_service import (
    apply_time_purchase,
)
from sqlalchemy.exc import IntegrityError

from app.services.usage_session_service import (
    GuestSessionStartConflictError,
    apply_guest_session_start,
)


class InactiveTimeProductError(Exception):
    pass


@dataclass(frozen=True)
class RegisteredTimeSaleResult:
    sale_id: UUID
    sale_type: str

    time_product_id: UUID
    product_name: str
    duration_seconds: int
    price_clp: int

    customer_id: UUID
    time_transaction_id: UUID

    available_seconds: int
    reserved_seconds: int

    created_at: datetime

@dataclass(frozen=True)
class GuestTimeSaleResult:
    sale_id: UUID
    sale_type: str

    time_product_id: UUID
    product_name: str
    duration_seconds: int
    price_clp: int

    station_id: UUID
    usage_session_id: UUID

    session_status: str
    station_status: str

    started_at: datetime
    created_at: datetime

def create_registered_time_sale(
    db: Session,
    *,
    time_product_id: UUID,
    customer_id: UUID,
    actor_user_id: UUID,
) -> RegisteredTimeSaleResult:
    try:
        product = db.scalar(
            select(TimeProduct)
            .where(
                TimeProduct.id == time_product_id
            )
            .with_for_update()
        )

        if product is None:
            raise TimeProductNotFoundError

        if not product.is_active:
            raise InactiveTimeProductError

        purchase = apply_time_purchase(
            db,
            customer_id=customer_id,
            seconds=product.duration_seconds,
            actor_user_id=actor_user_id,
        )

        sale = TimeSale(
            sale_type="REGISTERED",

            time_product_id=product.id,

            # Snapshot histórico
            product_name=product.name,
            duration_seconds=product.duration_seconds,
            price_clp=product.price_clp,

            actor_user_id=actor_user_id,

            customer_id=customer_id,
            station_id=None,

            time_transaction_id=(
                purchase.transaction_id
            ),
            usage_session_id=None,
        )

        db.add(sale)

        db.flush()
        db.refresh(sale)

        result = RegisteredTimeSaleResult(
            sale_id=sale.id,
            sale_type=sale.sale_type,

            time_product_id=sale.time_product_id,
            product_name=sale.product_name,
            duration_seconds=(
                sale.duration_seconds
            ),
            price_clp=sale.price_clp,

            customer_id=customer_id,
            time_transaction_id=(
                purchase.transaction_id
            ),

            available_seconds=(
                purchase.available_seconds
            ),
            reserved_seconds=(
                purchase.reserved_seconds
            ),

            created_at=sale.created_at,
        )

        db.commit()

        return result

    except Exception:
        db.rollback()
        raise
    
def create_guest_time_sale(
    db: Session,
    *,
    time_product_id: UUID,
    station_id: UUID,
    actor_user_id: UUID,
) -> GuestTimeSaleResult:
    try:
        product = db.scalar(
            select(TimeProduct)
            .where(
                TimeProduct.id == time_product_id
            )
            .with_for_update()
        )

        if product is None:
            raise TimeProductNotFoundError

        if not product.is_active:
            raise InactiveTimeProductError

        guest_session = apply_guest_session_start(
            db,
            station_id=station_id,
            authorized_seconds=(
                product.duration_seconds
            ),
        )

        sale = TimeSale(
            sale_type="GUEST",

            time_product_id=product.id,

            # Snapshot comercial inmutable.
            product_name=product.name,
            duration_seconds=(
                product.duration_seconds
            ),
            price_clp=product.price_clp,

            actor_user_id=actor_user_id,

            customer_id=None,
            station_id=station_id,
            time_transaction_id=None,
            usage_session_id=(
                guest_session.session_id
            ),
        )

        db.add(sale)

        db.flush()
        db.refresh(sale)

        result = GuestTimeSaleResult(
            sale_id=sale.id,
            sale_type=sale.sale_type,

            time_product_id=(
                sale.time_product_id
            ),
            product_name=sale.product_name,
            duration_seconds=(
                sale.duration_seconds
            ),
            price_clp=sale.price_clp,

            station_id=station_id,
            usage_session_id=(
                guest_session.session_id
            ),

            session_status=(
                guest_session.session_status
            ),
            station_status=(
                guest_session.station_status
            ),

            started_at=guest_session.started_at,
            created_at=sale.created_at,
        )

        db.commit()

        return result

    except IntegrityError as exc:
        db.rollback()

        raise GuestSessionStartConflictError from exc

    except Exception:
        db.rollback()
        raise