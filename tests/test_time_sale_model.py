import pytest

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.station import Station
from app.models.time_product import TimeProduct
from app.models.time_sale import TimeSale
from app.models.time_transaction import TimeTransaction
from app.models.time_wallet import TimeWallet
from app.models.usage_session import UsageSession


def create_product(db_session):
    product = TimeProduct(
        name="1 hora",
        duration_seconds=3600,
        price_clp=2000,
        is_active=True,
    )

    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)

    return product


def test_registered_sale_preserves_product_snapshot(
    db_session,
    user_factory,
):
    admin = user_factory(
        username="admin01",
        display_name="Administrador",
        role="ADMIN",
    )

    customer = user_factory(
        username="cliente01",
        display_name="Cliente",
        role="CUSTOMER",
    )

    product = create_product(db_session)

    wallet = db_session.scalar(
        select(TimeWallet).where(
            TimeWallet.user_id == customer.id
        )
    )

    transaction = TimeTransaction(
        wallet_id=wallet.id,
        transaction_type="PURCHASE",
        available_seconds_delta=3600,
        reserved_seconds_delta=0,
        actor_user_id=admin.id,
    )

    db_session.add(transaction)
    db_session.flush()

    sale = TimeSale(
        sale_type="REGISTERED",
        time_product_id=product.id,
        product_name=product.name,
        duration_seconds=product.duration_seconds,
        price_clp=product.price_clp,
        actor_user_id=admin.id,
        customer_id=customer.id,
        station_id=None,
        time_transaction_id=transaction.id,
        usage_session_id=None,
    )

    db_session.add(sale)
    db_session.commit()

    # El catálogo cambia después de la venta.
    product.name = "1 hora premium"
    product.duration_seconds = 4000
    product.price_clp = 2500

    db_session.commit()
    db_session.refresh(sale)

    # La venta conserva la realidad histórica.
    assert sale.product_name == "1 hora"
    assert sale.duration_seconds == 3600
    assert sale.price_clp == 2000
    assert sale.customer_id == customer.id
    assert sale.time_transaction_id == transaction.id


def test_guest_sale_links_usage_session_without_customer(
    db_session,
    user_factory,
):
    admin = user_factory(
        username="admin01",
        display_name="Administrador",
        role="ADMIN",
    )

    product = create_product(db_session)

    station = Station(
        code="PC-01",
        status="IN_USE",
    )

    db_session.add(station)
    db_session.flush()

    usage_session = UsageSession(
        station_id=station.id,
        user_id=None,
        session_type="GUEST",
        status="ACTIVE",
        authorized_seconds=product.duration_seconds,
    )

    db_session.add(usage_session)
    db_session.flush()

    sale = TimeSale(
        sale_type="GUEST",
        time_product_id=product.id,
        product_name=product.name,
        duration_seconds=product.duration_seconds,
        price_clp=product.price_clp,
        actor_user_id=admin.id,
        customer_id=None,
        station_id=station.id,
        time_transaction_id=None,
        usage_session_id=usage_session.id,
    )

    db_session.add(sale)
    db_session.commit()

    assert sale.sale_type == "GUEST"
    assert sale.customer_id is None
    assert sale.time_transaction_id is None
    assert sale.station_id == station.id
    assert sale.usage_session_id == usage_session.id


def test_registered_sale_requires_transaction(
    db_session,
    user_factory,
):
    admin = user_factory(
        username="admin01",
        display_name="Administrador",
        role="ADMIN",
    )

    customer = user_factory(
        username="cliente01",
        display_name="Cliente",
        role="CUSTOMER",
    )

    product = create_product(db_session)

    sale = TimeSale(
        sale_type="REGISTERED",
        time_product_id=product.id,
        product_name=product.name,
        duration_seconds=product.duration_seconds,
        price_clp=product.price_clp,
        actor_user_id=admin.id,
        customer_id=customer.id,
        station_id=None,
        time_transaction_id=None,
        usage_session_id=None,
    )

    db_session.add(sale)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_guest_sale_cannot_reference_customer(
    db_session,
    user_factory,
):
    admin = user_factory(
        username="admin01",
        display_name="Administrador",
        role="ADMIN",
    )

    customer = user_factory(
        username="cliente01",
        display_name="Cliente",
        role="CUSTOMER",
    )

    product = create_product(db_session)

    station = Station(
        code="PC-01",
        status="IN_USE",
    )

    db_session.add(station)
    db_session.flush()

    usage_session = UsageSession(
        station_id=station.id,
        user_id=None,
        session_type="GUEST",
        status="ACTIVE",
        authorized_seconds=3600,
    )

    db_session.add(usage_session)
    db_session.flush()

    sale = TimeSale(
        sale_type="GUEST",
        time_product_id=product.id,
        product_name=product.name,
        duration_seconds=3600,
        price_clp=2000,
        actor_user_id=admin.id,

        # Inválido para GUEST.
        customer_id=customer.id,

        station_id=station.id,
        time_transaction_id=None,
        usage_session_id=usage_session.id,
    )

    db_session.add(sale)

    with pytest.raises(IntegrityError):
        db_session.commit()