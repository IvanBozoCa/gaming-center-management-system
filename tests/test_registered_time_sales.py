import pytest

from sqlalchemy import select
from uuid import uuid4

from app.models.time_product import TimeProduct
from app.models.time_sale import TimeSale
from app.models.time_transaction import TimeTransaction
from app.models.time_wallet import TimeWallet
from app.services.time_product_service import (
    TimeProductNotFoundError,
)
from app.services.time_sale_service import (
    InactiveTimeProductError,
    create_registered_time_sale,
)
from app.services.time_wallet_service import (
    CustomerNotFoundError,
    InactiveCustomerError,
)


def create_product(
    db_session,
    *,
    name="1 hora",
    duration_seconds=3600,
    price_clp=2000,
    is_active=True,
):
    product = TimeProduct(
        name=name,
        duration_seconds=duration_seconds,
        price_clp=price_clp,
        is_active=is_active,
    )

    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)

    return product


def test_registered_sale_creates_sale_wallet_credit_and_ledger(
    db_session,
    user_factory,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    customer = user_factory(
        username="cliente01",
        available_seconds=1800,
    )

    product = create_product(
        db_session,
        duration_seconds=3600,
        price_clp=2500,
    )

    result = create_registered_time_sale(
        db_session,
        time_product_id=product.id,
        customer_id=customer.id,
        actor_user_id=admin.id,
    )

    assert result.sale_type == "REGISTERED"
    assert result.customer_id == customer.id
    assert result.time_product_id == product.id

    assert result.product_name == "1 hora"
    assert result.duration_seconds == 3600
    assert result.price_clp == 2500

    assert result.available_seconds == 5400
    assert result.reserved_seconds == 0

    wallet = db_session.scalar(
        select(TimeWallet).where(
            TimeWallet.user_id == customer.id
        )
    )

    assert wallet is not None
    assert wallet.available_seconds == 5400

    transaction = db_session.get(
        TimeTransaction,
        result.time_transaction_id,
    )

    assert transaction is not None
    assert transaction.transaction_type == "PURCHASE"
    assert transaction.available_seconds_delta == 3600
    assert transaction.reserved_seconds_delta == 0
    assert transaction.actor_user_id == admin.id

    sale = db_session.get(
        TimeSale,
        result.sale_id,
    )

    assert sale is not None
    assert sale.time_transaction_id == transaction.id
    assert sale.customer_id == customer.id
    assert sale.station_id is None
    assert sale.usage_session_id is None


def test_registered_sale_preserves_product_snapshot(
    db_session,
    user_factory,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    customer = user_factory(
        username="cliente01",
    )

    product = create_product(
        db_session,
        name="2 horas",
        duration_seconds=7200,
        price_clp=4000,
    )

    result = create_registered_time_sale(
        db_session,
        time_product_id=product.id,
        customer_id=customer.id,
        actor_user_id=admin.id,
    )

    sale = db_session.get(
        TimeSale,
        result.sale_id,
    )

    product.name = "2 horas premium"
    product.duration_seconds = 8000
    product.price_clp = 5000

    db_session.commit()
    db_session.refresh(sale)

    assert sale.product_name == "2 horas"
    assert sale.duration_seconds == 7200
    assert sale.price_clp == 4000


def test_registered_sale_rejects_unknown_product(
    db_session,
    user_factory,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    customer = user_factory(
        username="cliente01",
    )

    with pytest.raises(
        TimeProductNotFoundError
    ):
        create_registered_time_sale(
            db_session,
            time_product_id=uuid4(),
            customer_id=customer.id,
            actor_user_id=admin.id,
        )

    wallet = db_session.scalar(
        select(TimeWallet).where(
            TimeWallet.user_id == customer.id
        )
    )

    assert wallet.available_seconds == 0

    transactions = db_session.scalars(
        select(TimeTransaction).where(
            TimeTransaction.wallet_id == wallet.id
        )
    ).all()

    assert transactions == []

    sales = db_session.scalars(
        select(TimeSale)
    ).all()

    assert sales == []


def test_registered_sale_rejects_inactive_product(
    db_session,
    user_factory,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    customer = user_factory(
        username="cliente01",
    )

    product = create_product(
        db_session,
        is_active=False,
    )

    with pytest.raises(
        InactiveTimeProductError
    ):
        create_registered_time_sale(
            db_session,
            time_product_id=product.id,
            customer_id=customer.id,
            actor_user_id=admin.id,
        )

    wallet = db_session.scalar(
        select(TimeWallet).where(
            TimeWallet.user_id == customer.id
        )
    )

    assert wallet.available_seconds == 0

    assert db_session.scalars(
        select(TimeSale)
    ).all() == []


def test_registered_sale_rejects_unknown_customer(
    db_session,
    user_factory,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    product = create_product(
        db_session,
    )

    with pytest.raises(
        CustomerNotFoundError
    ):
        create_registered_time_sale(
            db_session,
            time_product_id=product.id,
            customer_id=uuid4(),
            actor_user_id=admin.id,
        )

    assert db_session.scalars(
        select(TimeSale)
    ).all() == []


def test_registered_sale_rejects_inactive_customer(
    db_session,
    user_factory,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    customer = user_factory(
        username="cliente01",
        is_active=False,
        available_seconds=1800,
    )

    product = create_product(
        db_session,
    )

    with pytest.raises(
        InactiveCustomerError
    ):
        create_registered_time_sale(
            db_session,
            time_product_id=product.id,
            customer_id=customer.id,
            actor_user_id=admin.id,
        )

    wallet = db_session.scalar(
        select(TimeWallet).where(
            TimeWallet.user_id == customer.id
        )
    )

    assert wallet.available_seconds == 1800

    assert db_session.scalars(
        select(TimeSale)
    ).all() == []


def test_registered_sale_rolls_back_purchase_if_sale_creation_fails(
    db_session,
    user_factory,
    monkeypatch,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    customer = user_factory(
        username="cliente01",
        available_seconds=1800,
    )

    product = create_product(
        db_session,
        duration_seconds=3600,
    )

    def fail_sale_creation(*args, **kwargs):
        raise RuntimeError(
            "Simulated TimeSale failure"
        )

    monkeypatch.setattr(
        "app.services.time_sale_service.TimeSale",
        fail_sale_creation,
    )

    with pytest.raises(
        RuntimeError,
        match="Simulated TimeSale failure",
    ):
        create_registered_time_sale(
            db_session,
            time_product_id=product.id,
            customer_id=customer.id,
            actor_user_id=admin.id,
        )

    wallet = db_session.scalar(
        select(TimeWallet).where(
            TimeWallet.user_id == customer.id
        )
    )

    assert wallet is not None
    assert wallet.available_seconds == 1800
    assert wallet.reserved_seconds == 0

    transactions = db_session.scalars(
        select(TimeTransaction).where(
            TimeTransaction.wallet_id == wallet.id
        )
    ).all()

    assert transactions == []