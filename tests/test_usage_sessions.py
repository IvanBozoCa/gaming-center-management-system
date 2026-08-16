from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.station import Station
from app.models.time_transaction import TimeTransaction
from app.models.time_wallet import TimeWallet
from app.models.usage_session import UsageSession
from app.services.usage_session_service import (
    SessionStartConflictError,
    start_registered_customer_session,
)


def _create_station(
    db_session,
    *,
    code: str = "PC-01",
    status: str = "AVAILABLE",
) -> Station:
    station = Station(
        code=code,
        status=status,
    )

    db_session.add(station)
    db_session.commit()
    db_session.refresh(station)

    return station


def _get_wallet(
    db_session,
    customer_id,
) -> TimeWallet:
    wallet = db_session.scalar(
        select(TimeWallet).where(
            TimeWallet.user_id
            == customer_id
        )
    )

    assert wallet is not None

    return wallet


def test_admin_can_start_registered_customer_session(
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
        available_seconds=7200,
    )

    station = _create_station(
        db_session,
    )

    response = client.post(
        "/admin/sessions",
        json={
            "station_id": str(station.id),
            "customer_id": str(customer.id),
            "authorized_seconds": 3600,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["station_id"] == str(
        station.id
    )
    assert data["customer_id"] == str(
        customer.id
    )
    assert data["authorized_seconds"] == 3600
    assert data["available_seconds"] == 3600
    assert data["reserved_seconds"] == 3600
    assert data["station_status"] == "IN_USE"
    assert data["session_id"]
    assert data["started_at"]

    db_session.expire_all()

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_station is not None
    assert stored_station.status == "IN_USE"

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    assert wallet.available_seconds == 3600
    assert wallet.reserved_seconds == 3600

    usage_session = db_session.scalar(
        select(UsageSession).where(
            UsageSession.id
            == data["session_id"]
        )
    )

    assert usage_session is not None
    assert usage_session.station_id == station.id
    assert usage_session.user_id == customer.id
    assert usage_session.status == "ACTIVE"
    assert usage_session.authorized_seconds == 3600
    assert usage_session.ended_at is None

    transactions = db_session.scalars(
        select(TimeTransaction).where(
            TimeTransaction.wallet_id
            == wallet.id
        )
    ).all()

    assert len(transactions) == 1

    transaction = transactions[0]

    assert (
        transaction.transaction_type
        == "SESSION_RESERVE"
    )
    assert (
        transaction.available_seconds_delta
        == -3600
    )
    assert (
        transaction.reserved_seconds_delta
        == 3600
    )
    assert transaction.actor_user_id == admin.id


def test_session_start_response_is_safe_for_admin_ui(
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
        available_seconds=3600,
    )

    station = _create_station(
        db_session,
    )

    response = client.post(
        "/admin/sessions",
        json={
            "station_id": str(station.id),
            "customer_id": str(customer.id),
            "authorized_seconds": 1800,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 201

    assert set(response.json().keys()) == {
        "session_id",
        "station_id",
        "customer_id",
        "authorized_seconds",
        "available_seconds",
        "reserved_seconds",
        "station_status",
        "started_at",
    }


def test_customer_cannot_start_session(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    actor = user_factory(
        username="cliente_actor",
    )

    customer = user_factory(
        username="cliente_target",
        available_seconds=3600,
    )

    station = _create_station(
        db_session,
    )

    response = client.post(
        "/admin/sessions",
        json={
            "station_id": str(station.id),
            "customer_id": str(customer.id),
            "authorized_seconds": 1800,
        },
        headers=auth_headers(actor),
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": "Admin privileges required"
    }


def test_session_start_requires_authentication(
    client,
    db_session,
    user_factory,
):
    customer = user_factory(
        username="cliente01",
        available_seconds=3600,
    )

    station = _create_station(
        db_session,
    )

    response = client.post(
        "/admin/sessions",
        json={
            "station_id": str(station.id),
            "customer_id": str(customer.id),
            "authorized_seconds": 1800,
        },
    )

    assert response.status_code == 401


def test_unknown_station_returns_404_without_changing_wallet(
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
        available_seconds=3600,
    )

    response = client.post(
        "/admin/sessions",
        json={
            "station_id": str(uuid4()),
            "customer_id": str(customer.id),
            "authorized_seconds": 1800,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Station not found"
    }

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    assert wallet.available_seconds == 3600
    assert wallet.reserved_seconds == 0


@pytest.mark.parametrize(
    "station_status",
    [
        "IN_USE",
        "MAINTENANCE",
        "OFFLINE",
    ],
)
def test_unavailable_station_returns_409(
    client,
    db_session,
    user_factory,
    auth_headers,
    station_status,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    customer = user_factory(
        username="cliente01",
        available_seconds=3600,
    )

    station = _create_station(
        db_session,
        status=station_status,
    )

    response = client.post(
        "/admin/sessions",
        json={
            "station_id": str(station.id),
            "customer_id": str(customer.id),
            "authorized_seconds": 1800,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 409

    assert response.json() == {
        "detail": "Station is not available"
    }

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    assert wallet.available_seconds == 3600
    assert wallet.reserved_seconds == 0


def test_unknown_customer_returns_404(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    station = _create_station(
        db_session,
    )

    response = client.post(
        "/admin/sessions",
        json={
            "station_id": str(station.id),
            "customer_id": str(uuid4()),
            "authorized_seconds": 1800,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Customer not found"
    }

    db_session.expire_all()

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_station is not None
    assert stored_station.status == "AVAILABLE"


def test_non_customer_target_returns_404(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    another_admin = user_factory(
        username="admin02",
        role="ADMIN",
    )

    station = _create_station(
        db_session,
    )

    response = client.post(
        "/admin/sessions",
        json={
            "station_id": str(station.id),
            "customer_id": str(
                another_admin.id
            ),
            "authorized_seconds": 1800,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Customer not found"
    }


def test_inactive_customer_returns_409(
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
        is_active=False,
        available_seconds=3600,
    )

    station = _create_station(
        db_session,
    )

    response = client.post(
        "/admin/sessions",
        json={
            "station_id": str(station.id),
            "customer_id": str(customer.id),
            "authorized_seconds": 1800,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 409

    assert response.json() == {
        "detail": "Customer is inactive"
    }

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    assert wallet.available_seconds == 3600
    assert wallet.reserved_seconds == 0


@pytest.mark.parametrize(
    "authorized_seconds",
    [
        0,
        -1,
        -3600,
    ],
)
def test_authorized_seconds_must_be_positive(
    client,
    db_session,
    user_factory,
    auth_headers,
    authorized_seconds,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    customer = user_factory(
        username="cliente01",
        available_seconds=3600,
    )

    station = _create_station(
        db_session,
    )

    response = client.post(
        "/admin/sessions",
        json={
            "station_id": str(station.id),
            "customer_id": str(customer.id),
            "authorized_seconds": (
                authorized_seconds
            ),
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 422


def test_insufficient_balance_rolls_back_entire_operation(
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

    station = _create_station(
        db_session,
    )

    response = client.post(
        "/admin/sessions",
        json={
            "station_id": str(station.id),
            "customer_id": str(customer.id),
            "authorized_seconds": 3600,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 409

    assert response.json() == {
        "detail": "Insufficient time balance"
    }

    db_session.expire_all()

    station = db_session.get(
        Station,
        station.id,
    )

    assert station is not None
    assert station.status == "AVAILABLE"

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    assert wallet.available_seconds == 1800
    assert wallet.reserved_seconds == 0

    sessions = db_session.scalars(
        select(UsageSession).where(
            UsageSession.user_id
            == customer.id
        )
    ).all()

    assert sessions == []

    transactions = db_session.scalars(
        select(TimeTransaction).where(
            TimeTransaction.wallet_id
            == wallet.id
        )
    ).all()

    assert transactions == []


def test_station_cannot_have_two_active_sessions(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    customer_one = user_factory(
        username="cliente01",
        available_seconds=7200,
    )

    customer_two = user_factory(
        username="cliente02",
        available_seconds=7200,
    )

    station = _create_station(
        db_session,
    )

    first_response = client.post(
        "/admin/sessions",
        json={
            "station_id": str(station.id),
            "customer_id": str(
                customer_one.id
            ),
            "authorized_seconds": 3600,
        },
        headers=auth_headers(admin),
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/admin/sessions",
        json={
            "station_id": str(station.id),
            "customer_id": str(
                customer_two.id
            ),
            "authorized_seconds": 3600,
        },
        headers=auth_headers(admin),
    )

    assert second_response.status_code == 409

    assert second_response.json() == {
        "detail": "Station is not available"
    }

    active_sessions = db_session.scalars(
        select(UsageSession).where(
            UsageSession.station_id
            == station.id,
            UsageSession.status
            == "ACTIVE",
        )
    ).all()

    assert len(active_sessions) == 1


def test_customer_cannot_have_two_active_sessions(
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
        available_seconds=7200,
    )

    station_one = _create_station(
        db_session,
        code="PC-01",
    )

    station_two = _create_station(
        db_session,
        code="PC-02",
    )

    first_response = client.post(
        "/admin/sessions",
        json={
            "station_id": str(
                station_one.id
            ),
            "customer_id": str(
                customer.id
            ),
            "authorized_seconds": 1800,
        },
        headers=auth_headers(admin),
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/admin/sessions",
        json={
            "station_id": str(
                station_two.id
            ),
            "customer_id": str(
                customer.id
            ),
            "authorized_seconds": 1800,
        },
        headers=auth_headers(admin),
    )

    assert second_response.status_code == 409

    assert second_response.json() == {
        "detail": (
            "Customer already has "
            "an active session"
        )
    }

    db_session.expire_all()

    station_two = db_session.get(
        Station,
        station_two.id,
    )

    assert station_two is not None
    assert station_two.status == "AVAILABLE"

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    assert wallet.available_seconds == 5400
    assert wallet.reserved_seconds == 1800


def test_database_rejects_two_active_sessions_for_same_station(
    db_session,
    user_factory,
):
    customer_one = user_factory(
        username="cliente01",
    )

    customer_two = user_factory(
        username="cliente02",
    )

    station = _create_station(
        db_session,
    )

    first_session = UsageSession(
        station_id=station.id,
        user_id=customer_one.id,
        status="ACTIVE",
        authorized_seconds=1800,
    )

    db_session.add(first_session)
    db_session.commit()

    second_session = UsageSession(
        station_id=station.id,
        user_id=customer_two.id,
        status="ACTIVE",
        authorized_seconds=1800,
    )

    db_session.add(second_session)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_database_rejects_two_active_sessions_for_same_customer(
    db_session,
    user_factory,
):
    customer = user_factory(
        username="cliente01",
    )

    station_one = _create_station(
        db_session,
        code="PC-01",
    )

    station_two = _create_station(
        db_session,
        code="PC-02",
    )

    first_session = UsageSession(
        station_id=station_one.id,
        user_id=customer.id,
        status="ACTIVE",
        authorized_seconds=1800,
    )

    db_session.add(first_session)
    db_session.commit()

    second_session = UsageSession(
        station_id=station_two.id,
        user_id=customer.id,
        status="ACTIVE",
        authorized_seconds=1800,
    )

    db_session.add(second_session)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_session_start_rolls_back_everything_if_ledger_insert_fails(
    db_session,
    user_factory,
):
    customer = user_factory(
        username="cliente01",
        available_seconds=7200,
    )

    station = _create_station(
        db_session,
    )

    invalid_actor_id = uuid4()

    with pytest.raises(
        SessionStartConflictError
    ):
        start_registered_customer_session(
            db_session,
            station_id=station.id,
            customer_id=customer.id,
            authorized_seconds=3600,
            actor_user_id=invalid_actor_id,
        )

    db_session.expire_all()

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_station is not None
    assert stored_station.status == "AVAILABLE"

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    assert wallet.available_seconds == 7200
    assert wallet.reserved_seconds == 0

    sessions = db_session.scalars(
        select(UsageSession).where(
            UsageSession.user_id
            == customer.id
        )
    ).all()

    assert sessions == []

    transactions = db_session.scalars(
        select(TimeTransaction).where(
            TimeTransaction.wallet_id
            == wallet.id
        )
    ).all()

    assert transactions == []