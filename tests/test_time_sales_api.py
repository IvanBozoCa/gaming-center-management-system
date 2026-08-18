from uuid import uuid4

from sqlalchemy import select

from app.models.station import Station
from app.models.time_product import TimeProduct
from app.models.time_sale import TimeSale
from app.models.time_transaction import TimeTransaction
from app.models.time_wallet import TimeWallet
from app.models.usage_session import UsageSession


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


def test_admin_can_register_registered_time_sale(
    client,
    db_session,
    user_factory,
    auth_headers,
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

    response = client.post(
        "/admin/time-sales",
        json={
            "sale_type": "REGISTERED",
            "time_product_id": str(product.id),
            "customer_id": str(customer.id),
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["sale_type"] == "REGISTERED"
    assert data["time_product_id"] == str(product.id)
    assert data["customer_id"] == str(customer.id)

    assert data["product_name"] == "1 hora"
    assert data["duration_seconds"] == 3600
    assert data["price_clp"] == 2500

    assert data["available_seconds"] == 5400
    assert data["reserved_seconds"] == 0

    assert data["sale_id"]
    assert data["time_transaction_id"]
    assert data["created_at"]

    wallet = db_session.scalar(
        select(TimeWallet).where(
            TimeWallet.user_id == customer.id
        )
    )

    assert wallet.available_seconds == 5400

    sale = db_session.get(
        TimeSale,
        data["sale_id"],
    )

    assert sale is not None
    assert sale.sale_type == "REGISTERED"

    transaction = db_session.get(
        TimeTransaction,
        data["time_transaction_id"],
    )

    assert transaction is not None
    assert transaction.transaction_type == "PURCHASE"


def test_admin_can_register_guest_time_sale(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    product = create_product(
        db_session,
        duration_seconds=7200,
        price_clp=4000,
    )

    station = create_station(
        db_session,
    )

    response = client.post(
        "/admin/time-sales",
        json={
            "sale_type": "GUEST",
            "time_product_id": str(product.id),
            "station_id": str(station.id),
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["sale_type"] == "GUEST"
    assert data["time_product_id"] == str(product.id)
    assert data["station_id"] == str(station.id)

    assert data["product_name"] == "1 hora"
    assert data["duration_seconds"] == 7200
    assert data["price_clp"] == 4000

    assert data["session_status"] == "ACTIVE"
    assert data["station_status"] == "IN_USE"

    assert data["sale_id"]
    assert data["usage_session_id"]

    session = db_session.get(
        UsageSession,
        data["usage_session_id"],
    )

    assert session is not None
    assert session.session_type == "GUEST"
    assert session.user_id is None
    assert session.authorized_seconds == 7200

    db_session.refresh(station)

    assert station.status == "IN_USE"

    assert db_session.scalars(
        select(TimeTransaction)
    ).all() == []


def test_customer_cannot_register_time_sale(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    customer = user_factory(
        username="cliente01",
    )

    product = create_product(
        db_session,
    )

    response = client.post(
        "/admin/time-sales",
        json={
            "sale_type": "REGISTERED",
            "time_product_id": str(product.id),
            "customer_id": str(customer.id),
        },
        headers=auth_headers(customer),
    )

    assert response.status_code == 403


def test_time_sale_without_authentication_returns_401(
    client,
    db_session,
    user_factory,
):
    customer = user_factory(
        username="cliente01",
    )

    product = create_product(
        db_session,
    )

    response = client.post(
        "/admin/time-sales",
        json={
            "sale_type": "REGISTERED",
            "time_product_id": str(product.id),
            "customer_id": str(customer.id),
        },
    )

    assert response.status_code == 401


def test_registered_sale_rejects_station_id(
    client,
    db_session,
    user_factory,
    auth_headers,
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
    )

    station = create_station(
        db_session,
    )

    response = client.post(
        "/admin/time-sales",
        json={
            "sale_type": "REGISTERED",
            "time_product_id": str(product.id),
            "customer_id": str(customer.id),
            "station_id": str(station.id),
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 422


def test_guest_sale_requires_station_id(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    product = create_product(
        db_session,
    )

    response = client.post(
        "/admin/time-sales",
        json={
            "sale_type": "GUEST",
            "time_product_id": str(product.id),
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 422


def test_time_sale_unknown_product_returns_404(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    customer = user_factory(
        username="cliente01",
    )

    response = client.post(
        "/admin/time-sales",
        json={
            "sale_type": "REGISTERED",
            "time_product_id": str(uuid4()),
            "customer_id": str(customer.id),
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Time product not found"
    }


def test_time_sale_inactive_product_returns_409(
    client,
    db_session,
    user_factory,
    auth_headers,
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

    response = client.post(
        "/admin/time-sales",
        json={
            "sale_type": "REGISTERED",
            "time_product_id": str(product.id),
            "customer_id": str(customer.id),
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 409

    assert response.json() == {
        "detail": "Time product is inactive"
    }


def test_guest_sale_unavailable_station_returns_409(
    client,
    db_session,
    user_factory,
    auth_headers,
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

    response = client.post(
        "/admin/time-sales",
        json={
            "sale_type": "GUEST",
            "time_product_id": str(product.id),
            "station_id": str(station.id),
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 409

    assert response.json() == {
        "detail": "Station is unavailable"
    }

    db_session.refresh(station)

    assert station.status == "MAINTENANCE"

    assert db_session.scalars(
        select(TimeSale)
    ).all() == []