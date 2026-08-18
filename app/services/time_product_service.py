from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.time_product import TimeProduct


class InvalidTimeProductNameError(Exception):
    pass


class TimeProductAlreadyExistsError(Exception):
    pass


class TimeProductNotFoundError(Exception):
    pass


def normalize_time_product_name(
    name: str,
) -> str:
    normalized_name = " ".join(
        name.strip().split()
    )

    if (
        not normalized_name
        or len(normalized_name) > 100
    ):
        raise InvalidTimeProductNameError

    return normalized_name


def get_time_product(
    db: Session,
    *,
    time_product_id: UUID,
) -> TimeProduct:
    time_product = db.get(
        TimeProduct,
        time_product_id,
    )

    if time_product is None:
        raise TimeProductNotFoundError

    return time_product


def create_time_product(
    db: Session,
    *,
    name: str,
    duration_seconds: int,
    price_clp: int,
) -> TimeProduct:
    normalized_name = normalize_time_product_name(
        name
    )

    existing_product = db.scalar(
        select(TimeProduct).where(
            TimeProduct.name == normalized_name
        )
    )

    if existing_product is not None:
        raise TimeProductAlreadyExistsError

    time_product = TimeProduct(
        name=normalized_name,
        duration_seconds=duration_seconds,
        price_clp=price_clp,
        is_active=True,
    )

    db.add(time_product)

    try:
        db.commit()

    except IntegrityError as exc:
        db.rollback()
        raise TimeProductAlreadyExistsError from exc

    except Exception:
        db.rollback()
        raise

    db.refresh(time_product)

    return time_product


def list_time_products(
    db: Session,
    *,
    is_active: bool | None = None,
) -> list[TimeProduct]:
    statement = select(TimeProduct)

    if is_active is not None:
        statement = statement.where(
            TimeProduct.is_active == is_active
        )

    statement = statement.order_by(
        TimeProduct.name
    )

    return list(
        db.scalars(statement).all()
    )


def update_time_product(
    db: Session,
    *,
    time_product_id: UUID,
    changes: dict[str, object],
) -> TimeProduct:
    try:
        time_product = db.scalar(
            select(TimeProduct)
            .where(
                TimeProduct.id == time_product_id
            )
            .with_for_update()
        )

        if time_product is None:
            raise TimeProductNotFoundError

        if "name" in changes:
            normalized_name = (
                normalize_time_product_name(
                    str(changes["name"])
                )
            )

            existing_product = db.scalar(
                select(TimeProduct).where(
                    TimeProduct.name
                    == normalized_name,
                    TimeProduct.id
                    != time_product.id,
                )
            )

            if existing_product is not None:
                raise TimeProductAlreadyExistsError

            time_product.name = normalized_name

        if "duration_seconds" in changes:
            time_product.duration_seconds = int(
                changes["duration_seconds"]
            )

        if "price_clp" in changes:
            time_product.price_clp = int(
                changes["price_clp"]
            )

        if "is_active" in changes:
            time_product.is_active = bool(
                changes["is_active"]
            )

        db.commit()
        db.refresh(time_product)

        return time_product

    except IntegrityError as exc:
        db.rollback()
        raise TimeProductAlreadyExistsError from exc

    except Exception:
        db.rollback()
        raise