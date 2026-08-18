import pytest

from sqlalchemy import select

from app.models.station import Station
from app.models.time_product import TimeProduct
from app.models.time_sale import TimeSale
from app.models.time_transaction import TimeTransaction
from app.models.time_wallet import TimeWallet
from app.models.usage_session import UsageSession
from app.models.user import User

from app.services.time_sale_service import (
    InactiveTimeProductError,
    create_guest_time_sale,
)
from app.services.usage_session_service import (
    SessionStationUnavailableError,
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


def create_station(
    db_session,
    *,
    code="PC-01",
    status="AVAILABLE",
):
    station = Station(
        code=code,
        status=status,
    )

    db_session.add(station)
    db_session.commit()
    db_session.refresh(station)

    return station


def test_guest_sale_creates_sale_session_and_occupies_station(
    db_session,
    user_factory,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    product = create_product(
        db_session,
        duration_seconds=3600,
        price_clp=2500,
    )

    station = create_station(
        db_session,
    )

    result = create_guest_time_sale(
        db_session,
        time_product_id=product.id,
        station_id=station.id,
        actor_user_id=admin.id,
    )

    assert result.sale_type == "GUEST"

    assert result.product_name == "1 hora"
    assert result.duration_seconds == 3600
    assert result.price_clp == 2500

    assert result.station_id == station.id

    assert result.session_status == "ACTIVE"
    assert result.station_status == "IN_USE"

    usage_session = db_session.get(
        UsageSession,
        result.usage_session_id,
    )

    assert usage_session is not None
    assert usage_session.session_type == "GUEST"
    assert usage_session.status == "ACTIVE"
    assert usage_session.user_id is None
    assert usage_session.station_id == station.id
    assert usage_session.authorized_seconds == 3600

    db_session.refresh(station)

    assert station.status == "IN_USE"

    sale = db_session.get(
        TimeSale,
        result.sale_id,
    )

    assert sale is not None
    assert sale.sale_type == "GUEST"

    assert sale.customer_id is None
    assert sale.time_transaction_id is None

    assert sale.station_id == station.id
    assert (
        sale.usage_session_id
        == usage_session.id
    )


def test_guest_sale_does_not_create_wallet_or_time_transaction(
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

    station = create_station(
        db_session,
    )

    create_guest_time_sale(
        db_session,
        time_product_id=product.id,
        station_id=station.id,
        actor_user_id=admin.id,
    )

    transactions = db_session.scalars(
        select(TimeTransaction)
    ).all()

    assert transactions == []

    wallets = db_session.scalars(
        select(TimeWallet)
    ).all()

    assert wallets == []

    users = db_session.scalars(
        select(User)
    ).all()

    # Solo existe el administrador.
    assert len(users) == 1
    assert users[0].id == admin.id


def test_guest_sale_preserves_product_snapshot(
    db_session,
    user_factory,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    product = create_product(
        db_session,
        name="2 horas",
        duration_seconds=7200,
        price_clp=4000,
    )

    station = create_station(
        db_session,
    )

    result = create_guest_time_sale(
        db_session,
        time_product_id=product.id,
        station_id=station.id,
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


def test_guest_sale_rejects_inactive_product_without_occupying_station(
    db_session,
    user_factory,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    product = create_product(
        db_session,
        is_active=False,
    )

    station = create_station(
        db_session,
    )

    with pytest.raises(
        InactiveTimeProductError
    ):
        create_guest_time_sale(
            db_session,
            time_product_id=product.id,
            station_id=station.id,
            actor_user_id=admin.id,
        )

    db_session.refresh(station)

    assert station.status == "AVAILABLE"

    assert db_session.scalars(
        select(TimeSale)
    ).all() == []

    assert db_session.scalars(
        select(UsageSession)
    ).all() == []


def test_guest_sale_rejects_unavailable_station(
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

    station = create_station(
        db_session,
        status="MAINTENANCE",
    )

    with pytest.raises(
        SessionStationUnavailableError
    ):
        create_guest_time_sale(
            db_session,
            time_product_id=product.id,
            station_id=station.id,
            actor_user_id=admin.id,
        )

    db_session.refresh(station)

    assert station.status == "MAINTENANCE"

    assert db_session.scalars(
        select(TimeSale)
    ).all() == []

    assert db_session.scalars(
        select(UsageSession)
    ).all() == []


def test_guest_sale_rolls_back_session_and_station_if_sale_fails(
    db_session,
    user_factory,
    monkeypatch,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    product = create_product(
        db_session,
    )

    station = create_station(
        db_session,
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
        create_guest_time_sale(
            db_session,
            time_product_id=product.id,
            station_id=station.id,
            actor_user_id=admin.id,
        )

    db_session.refresh(station)

    # El cambio IN_USE también debe revertirse.
    assert station.status == "AVAILABLE"

    sessions = db_session.scalars(
        select(UsageSession)
    ).all()

    assert sessions == []

    sales = db_session.scalars(
        select(TimeSale)
    ).all()

    assert sales == []

    transactions = db_session.scalars(
        select(TimeTransaction)
    ).all()

    assert transactions == []