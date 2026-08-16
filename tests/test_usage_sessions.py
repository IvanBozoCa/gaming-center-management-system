from uuid import uuid4
from datetime import (
    datetime,
    timedelta,
    timezone,
)
import pytest
from threading import Event, Thread
from sqlalchemy.orm import Session
from sqlalchemy import (
    event,
    func,
    select,
)
from sqlalchemy.exc import IntegrityError
import time
from app.models.station import Station
from app.models.time_transaction import TimeTransaction
from app.models.time_wallet import TimeWallet
from app.models.usage_session import UsageSession
from app.services.usage_session_service import (
    SessionExtensionConflictError,
    SessionFinishConflictError,
    SessionStartConflictError,
    _calculate_elapsed_seconds,
    extend_registered_customer_session,
    finish_registered_customer_session,
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


def _prepare_active_session(
    db_session,
    user_factory,
    *,
    authorized_seconds: int = 3600,
    available_seconds: int = 7200,
    elapsed_seconds: int = 900,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    customer = user_factory(
        username="cliente01",
        available_seconds=available_seconds,
    )

    station = _create_station(
        db_session,
    )

    start_result = (
        start_registered_customer_session(
            db_session,
            station_id=station.id,
            customer_id=customer.id,
            authorized_seconds=(
                authorized_seconds
            ),
            actor_user_id=admin.id,
        )
    )

    usage_session = db_session.get(
        UsageSession,
        start_result.session_id,
    )

    assert usage_session is not None

    database_now = db_session.scalar(
        select(
            func.clock_timestamp()
        )
    )

    assert database_now is not None

    usage_session.started_at = (
        database_now
        - timedelta(
            seconds=elapsed_seconds
        )
    )

    db_session.commit()
    db_session.refresh(usage_session)

    return (
        admin,
        customer,
        station,
        usage_session,
    )


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
    
    
def test_session_started_at_uses_actual_insert_time(
    db_session,
    user_factory,
):
    customer = user_factory(
        username="cliente01",
    )

    station = _create_station(
        db_session,
    )

    transaction_started_at = db_session.scalar(
        select(
            func.transaction_timestamp()
        )
    )

    db_session.execute(
        select(
            func.pg_sleep(0.05)
        )
    )

    usage_session = UsageSession(
        station_id=station.id,
        user_id=customer.id,
        status="ACTIVE",
        authorized_seconds=1800,
    )

    db_session.add(usage_session)
    db_session.flush()
    db_session.refresh(usage_session)

    assert usage_session.started_at > (
        transaction_started_at
    )

    db_session.rollback()
    
def test_admin_can_finish_session_with_partial_usage(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
        authorized_seconds=3600,
        available_seconds=7200,
        elapsed_seconds=900,
    )

    response = client.post(
        (
            f"/admin/sessions/"
            f"{usage_session.id}/finish"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    data = response.json()

    consumed = data["consumed_seconds"]
    released = data["released_seconds"]

    assert 900 <= consumed <= 905

    assert released == (
        3600 - consumed
    )

    assert data["authorized_seconds"] == 3600
    assert data["available_seconds"] == (
        7200 - consumed
    )
    assert data["reserved_seconds"] == 0

    assert data["session_status"] == "FINISHED"
    assert data["station_status"] == "AVAILABLE"

    db_session.expire_all()

    stored_session = db_session.get(
        UsageSession,
        usage_session.id,
    )

    assert stored_session is not None
    assert stored_session.status == "FINISHED"
    assert (
        stored_session.consumed_seconds
        == consumed
    )
    assert stored_session.ended_at is not None

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

    assert wallet.available_seconds == (
        7200 - consumed
    )
    assert wallet.reserved_seconds == 0

    transactions = db_session.scalars(
        select(TimeTransaction).where(
            TimeTransaction.wallet_id
            == wallet.id
        )
    ).all()

    transaction_by_type = {
        transaction.transaction_type:
        transaction
        for transaction in transactions
    }

    assert set(
        transaction_by_type
    ) == {
        "SESSION_RESERVE",
        "SESSION_USAGE",
        "SESSION_RELEASE",
    }

    usage_transaction = (
        transaction_by_type[
            "SESSION_USAGE"
        ]
    )

    assert (
        usage_transaction.available_seconds_delta
        == 0
    )
    assert (
        usage_transaction.reserved_seconds_delta
        == -consumed
    )

    release_transaction = (
        transaction_by_type[
            "SESSION_RELEASE"
        ]
    )

    assert (
        release_transaction.available_seconds_delta
        == released
    )
    assert (
        release_transaction.reserved_seconds_delta
        == -released
    )


def test_session_consumption_is_capped_at_authorized_time(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
        authorized_seconds=60,
        available_seconds=3600,
        elapsed_seconds=120,
    )

    response = client.post(
        (
            f"/admin/sessions/"
            f"{usage_session.id}/finish"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["authorized_seconds"] == 60
    assert data["consumed_seconds"] == 60
    assert data["released_seconds"] == 0
    assert data["available_seconds"] == 3540
    assert data["reserved_seconds"] == 0

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    transactions = db_session.scalars(
        select(TimeTransaction).where(
            TimeTransaction.wallet_id
            == wallet.id
        )
    ).all()

    transaction_types = {
        transaction.transaction_type
        for transaction in transactions
    }

    assert "SESSION_USAGE" in transaction_types
    assert "SESSION_RELEASE" not in transaction_types


def test_session_consumption_never_becomes_negative(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
        authorized_seconds=60,
        available_seconds=3600,
        elapsed_seconds=-60,
    )

    response = client.post(
        (
            f"/admin/sessions/"
            f"{usage_session.id}/finish"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["consumed_seconds"] == 0
    assert data["released_seconds"] == 60

    assert data["available_seconds"] == 3600
    assert data["reserved_seconds"] == 0

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    transactions = db_session.scalars(
        select(TimeTransaction).where(
            TimeTransaction.wallet_id
            == wallet.id
        )
    ).all()

    transaction_types = {
        transaction.transaction_type
        for transaction in transactions
    }

    assert "SESSION_RELEASE" in transaction_types
    assert "SESSION_USAGE" not in transaction_types


def test_customer_cannot_finish_session(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
    )

    response = client.post(
        (
            f"/admin/sessions/"
            f"{usage_session.id}/finish"
        ),
        headers=auth_headers(customer),
    )

    assert response.status_code == 403

    db_session.expire_all()

    stored_session = db_session.get(
        UsageSession,
        usage_session.id,
    )

    assert stored_session is not None
    assert stored_session.status == "ACTIVE"

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_station is not None
    assert stored_station.status == "IN_USE"


def test_unknown_session_finish_returns_404(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.post(
        (
            f"/admin/sessions/"
            f"{uuid4()}/finish"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Usage session not found"
    }


def test_finished_session_cannot_be_settled_twice(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
        authorized_seconds=3600,
        available_seconds=7200,
        elapsed_seconds=900,
    )

    first_response = client.post(
        (
            f"/admin/sessions/"
            f"{usage_session.id}/finish"
        ),
        headers=auth_headers(admin),
    )

    assert first_response.status_code == 200

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    transaction_count_before = len(
        db_session.scalars(
            select(TimeTransaction).where(
                TimeTransaction.wallet_id
                == wallet.id
            )
        ).all()
    )

    second_response = client.post(
        (
            f"/admin/sessions/"
            f"{usage_session.id}/finish"
        ),
        headers=auth_headers(admin),
    )

    assert second_response.status_code == 409

    assert second_response.json() == {
        "detail": (
            "Usage session is already finished"
        )
    }

    db_session.expire_all()

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    transaction_count_after = len(
        db_session.scalars(
            select(TimeTransaction).where(
                TimeTransaction.wallet_id
                == wallet.id
            )
        ).all()
    )

    assert (
        transaction_count_after
        == transaction_count_before
    )

    assert wallet.reserved_seconds == 0


def test_session_finish_rolls_back_everything_if_ledger_fails(
    db_session,
    user_factory,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
        authorized_seconds=3600,
        available_seconds=7200,
        elapsed_seconds=900,
    )

    invalid_actor_id = uuid4()

    with pytest.raises(
        SessionFinishConflictError
    ):
        finish_registered_customer_session(
            db_session,
            session_id=usage_session.id,
            actor_user_id=invalid_actor_id,
        )

    db_session.expire_all()

    stored_session = db_session.get(
        UsageSession,
        usage_session.id,
    )

    assert stored_session is not None
    assert stored_session.status == "ACTIVE"
    assert stored_session.consumed_seconds is None
    assert stored_session.ended_at is None

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

    transactions = db_session.scalars(
        select(TimeTransaction).where(
            TimeTransaction.wallet_id
            == wallet.id
        )
    ).all()

    assert len(transactions) == 1

    assert (
        transactions[0].transaction_type
        == "SESSION_RESERVE"
    )
    
def test_finish_timestamp_is_captured_before_lock_waits(
    db_session,
    user_factory,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
        authorized_seconds=60,
        available_seconds=3600,
        elapsed_seconds=10,
    )

    bind = db_session.get_bind()

    delayed_lock_queries = 0

    def delay_for_update(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        nonlocal delayed_lock_queries

        if "FOR UPDATE" in statement.upper():
            delayed_lock_queries += 1
            time.sleep(0.05)

    event.listen(
        bind,
        "before_cursor_execute",
        delay_for_update,
    )

    try:
        result = (
            finish_registered_customer_session(
                db_session,
                session_id=usage_session.id,
                actor_user_id=admin.id,
            )
        )
    finally:
        event.remove(
            bind,
            "before_cursor_execute",
            delay_for_update,
        )

    database_now = db_session.scalar(
        select(
            func.clock_timestamp()
        )
    )

    assert database_now is not None

    assert delayed_lock_queries >= 3

    elapsed_after_finish_timestamp = (
        database_now
        - result.ended_at
    ).total_seconds()

    assert (
        elapsed_after_finish_timestamp
        >= 0.10
    )
    

def test_admin_gets_empty_active_sessions_list(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.get(
        "/admin/sessions/active",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json() == []
    

def test_customer_cannot_list_active_sessions(
    client,
    user_factory,
    auth_headers,
):
    customer = user_factory(
        username="cliente01",
    )

    response = client.get(
        "/admin/sessions/active",
        headers=auth_headers(customer),
    )

    assert response.status_code == 403


def test_active_sessions_requires_authentication(
    client,
):
    response = client.get(
        "/admin/sessions/active",
    )

    assert response.status_code == 401


def test_admin_can_list_active_session_with_remaining_time(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
        authorized_seconds=3600,
        available_seconds=7200,
        elapsed_seconds=900,
    )

    response = client.get(
        "/admin/sessions/active",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    active_session = data[0]

    assert active_session["session_id"] == str(
        usage_session.id
    )
    assert active_session["station_id"] == str(
        station.id
    )
    assert (
        active_session["station_code"]
        == station.code
    )

    assert active_session["customer_id"] == str(
        customer.id
    )
    assert (
        active_session["customer_username"]
        == customer.username
    )
    assert (
        active_session["customer_display_name"]
        == customer.display_name
    )

    assert (
        active_session["authorized_seconds"]
        == 3600
    )

    elapsed = active_session[
        "elapsed_seconds"
    ]

    remaining = active_session[
        "remaining_seconds"
    ]

    assert 900 <= elapsed <= 905
    assert remaining == 3600 - elapsed
    assert active_session["time_state"] == "RUNNING"


def test_expired_active_session_reports_zero_remaining_time(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
        authorized_seconds=60,
        available_seconds=3600,
        elapsed_seconds=120,
    )

    response = client.get(
        "/admin/sessions/active",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    assert data[0]["elapsed_seconds"] == 60
    assert data[0]["remaining_seconds"] == 0
    assert data[0]["time_state"] == "EXHAUSTED"

    db_session.expire_all()

    stored_session = db_session.get(
        UsageSession,
        usage_session.id,
    )

    assert stored_session is not None
    assert stored_session.status == "ACTIVE"
    assert stored_session.ended_at is None
    assert stored_session.consumed_seconds is None

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

    assert wallet.available_seconds == 3540
    assert wallet.reserved_seconds == 60
    
    transactions = db_session.scalars(
    select(TimeTransaction).where(
        TimeTransaction.wallet_id
        == wallet.id
        )
    ).all()

    assert len(transactions) == 1

    assert (
        transactions[0].transaction_type
        == "SESSION_RESERVE"
    )


def test_finished_sessions_are_excluded_from_active_list(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
        authorized_seconds=3600,
        available_seconds=7200,
        elapsed_seconds=900,
    )

    finish_response = client.post(
        (
            f"/admin/sessions/"
            f"{usage_session.id}/finish"
        ),
        headers=auth_headers(admin),
    )

    assert finish_response.status_code == 200

    response = client.get(
        "/admin/sessions/active",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json() == []


def test_admin_can_list_multiple_active_sessions(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    (
        admin,
        customer_one,
        station_one,
        session_one,
    ) = _prepare_active_session(
        db_session,
        user_factory,
        authorized_seconds=3600,
        available_seconds=7200,
        elapsed_seconds=600,
    )

    customer_two = user_factory(
        username="cliente02",
        display_name="Cliente Dos",
        available_seconds=7200,
    )

    station_two = _create_station(
        db_session,
        code="PC-02",
    )

    second_result = (
        start_registered_customer_session(
            db_session,
            station_id=station_two.id,
            customer_id=customer_two.id,
            authorized_seconds=1800,
            actor_user_id=admin.id,
        )
    )

    second_session = db_session.get(
        UsageSession,
        second_result.session_id,
    )

    assert second_session is not None

    database_now = db_session.scalar(
        select(
            func.clock_timestamp()
        )
    )

    assert database_now is not None

    second_session.started_at = (
        database_now
        - timedelta(seconds=300)
    )

    db_session.commit()

    response = client.get(
        "/admin/sessions/active",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    session_ids = {
        item["session_id"]
        for item in data
    }

    assert session_ids == {
        str(session_one.id),
        str(second_session.id),
    }

    station_codes = {
        item["station_code"]
        for item in data
    }

    assert station_codes == {
        station_one.code,
        station_two.code,
    }


def test_listing_active_sessions_is_read_only(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
        authorized_seconds=3600,
        available_seconds=7200,
        elapsed_seconds=900,
    )

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    available_before = (
        wallet.available_seconds
    )
    reserved_before = (
        wallet.reserved_seconds
    )

    transactions_before = db_session.scalars(
        select(TimeTransaction).where(
            TimeTransaction.wallet_id
            == wallet.id
        )
    ).all()

    transaction_count_before = len(
        transactions_before
    )

    response = client.get(
        "/admin/sessions/active",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    db_session.expire_all()

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    stored_session = db_session.get(
        UsageSession,
        usage_session.id,
    )

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_session is not None
    assert stored_station is not None

    assert (
        wallet.available_seconds
        == available_before
    )
    assert (
        wallet.reserved_seconds
        == reserved_before
    )

    assert stored_session.status == "ACTIVE"
    assert stored_session.ended_at is None
    assert stored_session.consumed_seconds is None

    assert stored_station.status == "IN_USE"

    transactions_after = db_session.scalars(
        select(TimeTransaction).where(
            TimeTransaction.wallet_id
            == wallet.id
        )
    ).all()

    assert (
        len(transactions_after)
        == transaction_count_before
    )


def test_elapsed_seconds_uses_exact_integer_arithmetic():
    started_at = datetime(
        2026,
        8,
        16,
        12,
        0,
        0,
        tzinfo=timezone.utc,
    )

    ended_at = (
        started_at
        + timedelta(
            seconds=10,
            microseconds=999_999,
        )
    )

    result = _calculate_elapsed_seconds(
        started_at=started_at,
        ended_at=ended_at,
        authorized_seconds=60,
    )

    assert result == 10
    assert (
        _calculate_elapsed_seconds(
            started_at=started_at,
            ended_at=started_at
            - timedelta(seconds=5),
            authorized_seconds=60,
            ) == 0
        )

    assert (
        _calculate_elapsed_seconds(
            started_at=started_at,
            ended_at=started_at
            + timedelta(seconds=120),
            authorized_seconds=60,
            ) == 60
        )


def test_admin_can_extend_active_session(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
        authorized_seconds=3600,
        available_seconds=7200,
        elapsed_seconds=900,
    )

    started_at_before = usage_session.started_at

    response = client.post(
        f"/admin/sessions/{usage_session.id}/extend",
        json={
            "additional_seconds": 1800,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["session_id"] == str(
        usage_session.id
    )
    assert data["station_id"] == str(
        station.id
    )
    assert data["customer_id"] == str(
        customer.id
    )

    assert data["additional_seconds"] == 1800
    assert data["authorized_seconds"] == 5400
    assert data["available_seconds"] == 1800
    assert data["reserved_seconds"] == 5400
    assert data["session_status"] == "ACTIVE"

    db_session.expire_all()

    stored_session = db_session.get(
        UsageSession,
        usage_session.id,
    )

    assert stored_session is not None
    assert stored_session.status == "ACTIVE"
    assert stored_session.authorized_seconds == 5400
    assert stored_session.started_at == started_at_before

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    assert wallet.available_seconds == 1800
    assert wallet.reserved_seconds == 5400



def test_session_extension_creates_reserve_transaction(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
        authorized_seconds=3600,
        available_seconds=7200,
    )

    response = client.post(
        f"/admin/sessions/{usage_session.id}/extend",
        json={
            "additional_seconds": 1800,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    transactions = db_session.scalars(
        select(TimeTransaction).where(
            TimeTransaction.wallet_id
            == wallet.id,
            TimeTransaction.transaction_type
            == "SESSION_RESERVE",
        )
    ).all()

    assert len(transactions) == 2

    extension_transactions = [
        transaction
        for transaction in transactions
        if (
            transaction.available_seconds_delta
            == -1800
            and transaction.reserved_seconds_delta
            == 1800
        )
    ]

    assert len(extension_transactions) == 1

    assert (
        extension_transactions[0].actor_user_id
        == admin.id
    )


def test_multiple_session_extensions_accumulate(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
        authorized_seconds=1800,
        available_seconds=7200,
    )

    first_response = client.post(
        f"/admin/sessions/{usage_session.id}/extend",
        json={"additional_seconds": 600},
        headers=auth_headers(admin),
    )

    second_response = client.post(
        f"/admin/sessions/{usage_session.id}/extend",
        json={"additional_seconds": 1200},
        headers=auth_headers(admin),
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    db_session.expire_all()

    stored_session = db_session.get(
        UsageSession,
        usage_session.id,
    )

    assert stored_session is not None
    assert stored_session.authorized_seconds == 3600

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    assert wallet.available_seconds == 3600
    assert wallet.reserved_seconds == 3600
    
    
def test_session_extension_rejects_insufficient_balance(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
        authorized_seconds=3600,
        available_seconds=3600,
    )

    response = client.post(
        f"/admin/sessions/{usage_session.id}/extend",
        json={
            "additional_seconds": 60,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Insufficient time balance"
    }

    db_session.expire_all()

    stored_session = db_session.get(
        UsageSession,
        usage_session.id,
    )

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    assert stored_session is not None
    assert stored_session.authorized_seconds == 3600
    assert wallet.available_seconds == 0
    assert wallet.reserved_seconds == 3600
    
    
def test_finished_session_cannot_be_extended(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
        authorized_seconds=3600,
        available_seconds=7200,
        elapsed_seconds=900,
    )

    finish_response = client.post(
        f"/admin/sessions/{usage_session.id}/finish",
        headers=auth_headers(admin),
    )

    assert finish_response.status_code == 200

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    available_before = wallet.available_seconds
    reserved_before = wallet.reserved_seconds

    transaction_count_before = len(
        db_session.scalars(
            select(TimeTransaction).where(
                TimeTransaction.wallet_id
                == wallet.id
            )
        ).all()
    )

    response = client.post(
        f"/admin/sessions/{usage_session.id}/extend",
        json={
            "additional_seconds": 1800,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 409

    db_session.expire_all()

    stored_session = db_session.get(
        UsageSession,
        usage_session.id,
    )

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    assert stored_session is not None
    assert stored_session.status == "FINISHED"

    assert (
        wallet.available_seconds
        == available_before
    )
    assert (
        wallet.reserved_seconds
        == reserved_before
    )

    transaction_count_after = len(
        db_session.scalars(
            select(TimeTransaction).where(
                TimeTransaction.wallet_id
                == wallet.id
            )
        ).all()
    )

    assert (
        transaction_count_after
        == transaction_count_before
    )


@pytest.mark.parametrize(
    "additional_seconds",
    [0, -1, -300],
)
def test_session_extension_rejects_non_positive_time(
    client,
    db_session,
    user_factory,
    auth_headers,
    additional_seconds,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
    )

    response = client.post(
        f"/admin/sessions/{usage_session.id}/extend",
        json={
            "additional_seconds": additional_seconds,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 422



def test_unknown_session_extension_returns_404(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.post(
        f"/admin/sessions/{uuid4()}/extend",
        json={"additional_seconds": 1800},
        headers=auth_headers(admin),
    )

    assert response.status_code == 404


def test_customer_cannot_extend_session(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
    )

    response = client.post(
        f"/admin/sessions/{usage_session.id}/extend",
        json={"additional_seconds": 1800},
        headers=auth_headers(customer),
    )

    assert response.status_code == 403


def test_session_extension_requires_authentication(
    client,
    db_session,
    user_factory,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
    )

    response = client.post(
        f"/admin/sessions/{usage_session.id}/extend",
        json={"additional_seconds": 1800},
    )

    assert response.status_code == 401
    
    
def test_session_extension_rolls_back_if_ledger_fails(
    db_session,
    user_factory,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
        authorized_seconds=3600,
        available_seconds=7200,
    )

    original_started_at = usage_session.started_at

    with pytest.raises(
        SessionExtensionConflictError
    ):
        extend_registered_customer_session(
            db_session,
            session_id=usage_session.id,
            additional_seconds=1800,
            actor_user_id=uuid4(),
        )

    db_session.expire_all()

    stored_session = db_session.get(
        UsageSession,
        usage_session.id,
    )

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    assert stored_session is not None

    assert stored_session.status == "ACTIVE"
    assert stored_session.authorized_seconds == 3600
    assert stored_session.started_at == original_started_at

    assert wallet.available_seconds == 3600
    assert wallet.reserved_seconds == 3600


def test_finish_uses_extended_authorized_time(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
        authorized_seconds=3600,
        available_seconds=9000,
        elapsed_seconds=4500,
    )

    extend_response = client.post(
        f"/admin/sessions/{usage_session.id}/extend",
        json={
            "additional_seconds": 1800,
        },
        headers=auth_headers(admin),
    )

    assert extend_response.status_code == 200
    assert (
        extend_response.json()["authorized_seconds"]
        == 5400
    )

    finish_response = client.post(
        f"/admin/sessions/{usage_session.id}/finish",
        headers=auth_headers(admin),
    )

    assert finish_response.status_code == 200

    data = finish_response.json()

    assert data["authorized_seconds"] == 5400
    assert 4500 <= data["consumed_seconds"] <= 4505

    assert data["released_seconds"] == (
        5400 - data["consumed_seconds"]
    )

    assert data["reserved_seconds"] == 0


def test_extend_and_finish_are_serialized_by_session_lock(
    db_session,
    user_factory,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
        authorized_seconds=3600,
        available_seconds=9000,
        elapsed_seconds=4500,
    )

    bind = db_session.get_bind()

    extend_db = Session(
        bind=bind,
        autoflush=False,
        expire_on_commit=False,
    )

    finish_db = Session(
        bind=bind,
        autoflush=False,
        expire_on_commit=False,
    )

    extend_has_session_lock = Event()
    allow_extend_to_continue = Event()
    finish_attempted_session_lock = Event()

    results = {}
    errors = []

    def after_cursor_execute(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        role = conn.info.get(
            "session_concurrency_test_role"
        )

        normalized_statement = (
            " ".join(
                statement.upper().split()
            )
        )

        if (
            role == "extend"
            and "FOR UPDATE"
            in normalized_statement
            and "USAGE_SESSIONS"
            in normalized_statement
        ):
            extend_has_session_lock.set()

            if not allow_extend_to_continue.wait(
                timeout=5
            ):
                raise RuntimeError(
                    "Timed out waiting to "
                    "release extension lock"
                )

    def before_cursor_execute(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        role = conn.info.get(
            "session_concurrency_test_role"
        )

        normalized_statement = (
            " ".join(
                statement.upper().split()
            )
        )

        if (
            role == "finish"
            and "FOR UPDATE"
            in normalized_statement
            and "USAGE_SESSIONS"
            in normalized_statement
        ):
            finish_attempted_session_lock.set()

    def run_extension():
        try:
            connection = extend_db.connection()

            connection.info[
                "session_concurrency_test_role"
            ] = "extend"

            results["extend"] = (
                extend_registered_customer_session(
                    extend_db,
                    session_id=usage_session.id,
                    additional_seconds=1800,
                    actor_user_id=admin.id,
                )
            )

        except Exception as exc:
            errors.append(exc)

    def run_finish():
        try:
            connection = finish_db.connection()

            connection.info[
                "session_concurrency_test_role"
            ] = "finish"

            results["finish"] = (
                finish_registered_customer_session(
                    finish_db,
                    session_id=usage_session.id,
                    actor_user_id=admin.id,
                )
            )

        except Exception as exc:
            errors.append(exc)

    event.listen(
        bind,
        "after_cursor_execute",
        after_cursor_execute,
    )

    event.listen(
        bind,
        "before_cursor_execute",
        before_cursor_execute,
    )

    extend_thread = Thread(
        target=run_extension,
        daemon=True,
    )

    finish_thread = Thread(
        target=run_finish,
        daemon=True,
    )

    try:
        extend_thread.start()

        assert extend_has_session_lock.wait(
            timeout=5
        )

        finish_thread.start()

        assert finish_attempted_session_lock.wait(
            timeout=5
        )

        # FINISH ya intentó bloquear UsageSession,
        # pero EXTEND todavía conserva el lock.
        assert finish_thread.is_alive()

        allow_extend_to_continue.set()

        extend_thread.join(timeout=10)
        finish_thread.join(timeout=10)

    finally:
        allow_extend_to_continue.set()

        event.remove(
            bind,
            "after_cursor_execute",
            after_cursor_execute,
        )

        event.remove(
            bind,
            "before_cursor_execute",
            before_cursor_execute,
        )

        extend_thread.join(timeout=1)
        finish_thread.join(timeout=1)

        if not extend_thread.is_alive():
            extend_db.close()

        if not finish_thread.is_alive():
            finish_db.close()

    assert not extend_thread.is_alive()
    assert not finish_thread.is_alive()

    assert errors == []

    extension_result = results["extend"]
    finish_result = results["finish"]

    assert (
        extension_result.authorized_seconds
        == 5400
    )

    assert (
        finish_result.authorized_seconds
        == 5400
    )

    assert (
        3600
        < finish_result.consumed_seconds
        <= 5400
    )

    db_session.expire_all()

    stored_session = db_session.get(
        UsageSession,
        usage_session.id,
    )

    stored_station = db_session.get(
        Station,
        station.id,
    )

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    assert stored_session is not None
    assert stored_station is not None

    assert stored_session.status == "FINISHED"
    assert stored_session.authorized_seconds == 5400

    assert stored_station.status == "AVAILABLE"

    assert wallet.reserved_seconds == 0

    assert wallet.available_seconds == (
        9000
        - stored_session.consumed_seconds
    )

    reserve_transactions = db_session.scalars(
        select(TimeTransaction).where(
            TimeTransaction.wallet_id
            == wallet.id,
            TimeTransaction.transaction_type
            == "SESSION_RESERVE",
        )
    ).all()

    assert len(reserve_transactions) == 2


def test_exhausted_session_returns_to_running_after_extension(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    (
        admin,
        customer,
        station,
        usage_session,
    ) = _prepare_active_session(
        db_session,
        user_factory,
        authorized_seconds=60,
        available_seconds=3600,
        elapsed_seconds=120,
    )

    started_at_before = (
        usage_session.started_at
    )

    exhausted_response = client.get(
        "/admin/sessions/active",
        headers=auth_headers(admin),
    )

    assert exhausted_response.status_code == 200

    exhausted_data = (
        exhausted_response.json()[0]
    )

    assert (
        exhausted_data["remaining_seconds"]
        == 0
    )
    assert (
        exhausted_data["time_state"]
        == "EXHAUSTED"
    )

    extend_response = client.post(
        (
            f"/admin/sessions/"
            f"{usage_session.id}/extend"
        ),
        json={
            "additional_seconds": 600,
        },
        headers=auth_headers(admin),
    )

    assert extend_response.status_code == 200
    assert (
        extend_response.json()[
            "authorized_seconds"
        ]
        == 660
    )

    running_response = client.get(
        "/admin/sessions/active",
        headers=auth_headers(admin),
    )

    assert running_response.status_code == 200

    running_data = (
        running_response.json()[0]
    )

    assert (
        running_data["time_state"]
        == "RUNNING"
    )
    assert (
        running_data["remaining_seconds"]
        > 0
    )

    db_session.expire_all()

    stored_session = db_session.get(
        UsageSession,
        usage_session.id,
    )

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_session is not None
    assert stored_station is not None

    assert stored_session.status == "ACTIVE"
    assert (
        stored_session.authorized_seconds
        == 660
    )
    assert (
        stored_session.started_at
        == started_at_before
    )

    assert stored_station.status == "IN_USE"