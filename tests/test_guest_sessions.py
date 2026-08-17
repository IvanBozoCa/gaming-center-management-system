from datetime import timedelta
from threading import Event, Thread
from uuid import uuid4

import pytest
from sqlalchemy import (
    event,
    func,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.station import Station
from app.models.time_transaction import (
    TimeTransaction,
)
from app.models.time_wallet import TimeWallet
from app.models.usage_session import UsageSession
from app.models.user import User
from app.services.station_service import (
    StationInUseError,
    update_station_status,
)
from app.services.usage_session_service import (
    GuestSessionFinishConflictError,
    GuestSessionStartConflictError,
    SessionStationUnavailableError,
    finish_guest_session,
    start_guest_session,
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
    user_id,
) -> TimeWallet:
    wallet = db_session.scalar(
        select(TimeWallet).where(
            TimeWallet.user_id == user_id
        )
    )

    assert wallet is not None

    return wallet


def _count_rows(
    db_session,
    model,
) -> int:
    result = db_session.scalar(
        select(func.count())
        .select_from(model)
    )

    assert result is not None

    return result


def _move_session_into_past(
    db_session,
    usage_session,
    *,
    seconds: int,
):
    database_now = db_session.scalar(
        select(
            func.clock_timestamp()
        )
    )

    assert database_now is not None

    usage_session.started_at = (
        database_now
        - timedelta(seconds=seconds)
    )

    db_session.commit()
    db_session.refresh(usage_session)


def test_registered_session_requires_user_id(
    db_session,
):
    station = _create_station(
        db_session,
    )

    session = UsageSession(
        station_id=station.id,
        user_id=None,
        session_type="REGISTERED",
        status="ACTIVE",
        authorized_seconds=1800,
    )

    db_session.add(session)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_guest_session_requires_null_user_id(
    db_session,
    user_factory,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    station = _create_station(
        db_session,
    )

    session = UsageSession(
        station_id=station.id,
        user_id=admin.id,
        session_type="GUEST",
        status="ACTIVE",
        authorized_seconds=1800,
    )

    db_session.add(session)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_usage_session_rejects_unknown_session_type(
    db_session,
    user_factory,
):
    customer = user_factory(
        username="cliente01",
    )

    station = _create_station(
        db_session,
    )

    session = UsageSession(
        station_id=station.id,
        user_id=customer.id,
        session_type="UNKNOWN",
        status="ACTIVE",
        authorized_seconds=1800,
    )

    db_session.add(session)

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()


def test_registered_flow_creates_registered_session(
    db_session,
    user_factory,
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

    result = start_registered_customer_session(
        db_session,
        station_id=station.id,
        customer_id=customer.id,
        authorized_seconds=1800,
        actor_user_id=admin.id,
    )

    stored_session = db_session.get(
        UsageSession,
        result.session_id,
    )

    assert stored_session is not None
    assert (
        stored_session.session_type
        == "REGISTERED"
    )
    assert stored_session.user_id == customer.id


def test_admin_can_start_guest_session(
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
        "/admin/guest-sessions",
        json={
            "station_id": str(station.id),
            "authorized_seconds": 3600,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["station_id"] == str(
        station.id
    )
    assert data["authorized_seconds"] == 3600
    assert data["session_type"] == "GUEST"
    assert data["session_status"] == "ACTIVE"
    assert data["station_status"] == "IN_USE"
    assert data["started_at"]

    db_session.expire_all()

    stored_session = db_session.get(
        UsageSession,
        data["session_id"],
    )

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_session is not None
    assert stored_station is not None

    assert stored_session.session_type == "GUEST"
    assert stored_session.user_id is None
    assert stored_session.status == "ACTIVE"
    assert stored_session.authorized_seconds == 3600

    assert stored_station.status == "IN_USE"


def test_guest_start_does_not_create_user_wallet_or_ledger(
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

    users_before = _count_rows(
        db_session,
        User,
    )
    wallets_before = _count_rows(
        db_session,
        TimeWallet,
    )
    transactions_before = _count_rows(
        db_session,
        TimeTransaction,
    )

    response = client.post(
        "/admin/guest-sessions",
        json={
            "station_id": str(station.id),
            "authorized_seconds": 1800,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 201

    assert _count_rows(
        db_session,
        User,
    ) == users_before

    assert _count_rows(
        db_session,
        TimeWallet,
    ) == wallets_before

    assert _count_rows(
        db_session,
        TimeTransaction,
    ) == transactions_before


@pytest.mark.parametrize(
    "authorized_seconds",
    [
        0,
        -1,
        -3600,
    ],
)
def test_guest_start_rejects_non_positive_time(
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

    station = _create_station(
        db_session,
    )

    response = client.post(
        "/admin/guest-sessions",
        json={
            "station_id": str(station.id),
            "authorized_seconds": (
                authorized_seconds
            ),
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "station_status",
    [
        "MAINTENANCE",
        "OFFLINE",
        "IN_USE",
    ],
)
def test_guest_start_rejects_unavailable_station(
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

    station = _create_station(
        db_session,
        status=station_status,
    )

    response = client.post(
        "/admin/guest-sessions",
        json={
            "station_id": str(station.id),
            "authorized_seconds": 1800,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 409

    assert response.json() == {
        "detail": "Station is not available"
    }


def test_guest_start_unknown_station_returns_404(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.post(
        "/admin/guest-sessions",
        json={
            "station_id": str(uuid4()),
            "authorized_seconds": 1800,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 404


def test_customer_cannot_start_guest_session(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    customer = user_factory(
        username="cliente01",
    )

    station = _create_station(
        db_session,
    )

    response = client.post(
        "/admin/guest-sessions",
        json={
            "station_id": str(station.id),
            "authorized_seconds": 1800,
        },
        headers=auth_headers(customer),
    )

    assert response.status_code == 403


def test_guest_start_requires_authentication(
    client,
    db_session,
):
    station = _create_station(
        db_session,
    )

    response = client.post(
        "/admin/guest-sessions",
        json={
            "station_id": str(station.id),
            "authorized_seconds": 1800,
        },
    )

    assert response.status_code == 401


def test_guest_start_rejects_existing_active_session_even_if_station_says_available(
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

    station = _create_station(
        db_session,
        status="AVAILABLE",
    )

    existing_session = UsageSession(
        station_id=station.id,
        user_id=customer.id,
        session_type="REGISTERED",
        status="ACTIVE",
        authorized_seconds=1800,
    )

    db_session.add(existing_session)
    db_session.commit()

    response = client.post(
        "/admin/guest-sessions",
        json={
            "station_id": str(station.id),
            "authorized_seconds": 900,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 409

    assert response.json() == {
        "detail": (
            "Station already has "
            "an active session"
        )
    }

    db_session.expire_all()

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_station is not None
    assert stored_station.status == "AVAILABLE"

    active_sessions = db_session.scalars(
        select(UsageSession).where(
            UsageSession.station_id
            == station.id,
            UsageSession.status
            == "ACTIVE",
        )
    ).all()

    assert len(active_sessions) == 1


def test_admin_gets_empty_guest_active_list(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.get(
        "/admin/guest-sessions/active",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json() == []


def test_active_guest_reports_server_derived_time(
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

    start_response = client.post(
        "/admin/guest-sessions",
        json={
            "station_id": str(station.id),
            "authorized_seconds": 3600,
        },
        headers=auth_headers(admin),
    )

    assert start_response.status_code == 201

    session_id = start_response.json()[
        "session_id"
    ]

    usage_session = db_session.get(
        UsageSession,
        session_id,
    )

    assert usage_session is not None

    _move_session_into_past(
        db_session,
        usage_session,
        seconds=900,
    )

    response = client.get(
        "/admin/guest-sessions/active",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    guest = data[0]

    assert guest["session_id"] == session_id
    assert guest["station_id"] == str(
        station.id
    )
    assert guest["station_code"] == station.code
    assert guest["authorized_seconds"] == 3600

    elapsed = guest["elapsed_seconds"]

    assert 900 <= elapsed <= 905
    assert (
        guest["remaining_seconds"]
        == 3600 - elapsed
    )

    assert guest["time_state"] == "RUNNING"


def test_exhausted_guest_remains_active(
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

    result = start_guest_session(
        db_session,
        station_id=station.id,
        authorized_seconds=60,
    )

    usage_session = db_session.get(
        UsageSession,
        result.session_id,
    )

    assert usage_session is not None

    _move_session_into_past(
        db_session,
        usage_session,
        seconds=120,
    )

    response = client.get(
        "/admin/guest-sessions/active",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    guest = response.json()[0]

    assert guest["elapsed_seconds"] == 60
    assert guest["remaining_seconds"] == 0
    assert guest["time_state"] == "EXHAUSTED"

    db_session.expire_all()

    stored_session = db_session.get(
        UsageSession,
        result.session_id,
    )

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_session is not None
    assert stored_station is not None

    assert stored_session.status == "ACTIVE"
    assert stored_session.ended_at is None
    assert stored_session.consumed_seconds is None

    assert stored_station.status == "IN_USE"


def test_customer_cannot_list_active_guest_sessions(
    client,
    user_factory,
    auth_headers,
):
    customer = user_factory(
        username="cliente01",
    )

    response = client.get(
        "/admin/guest-sessions/active",
        headers=auth_headers(customer),
    )

    assert response.status_code == 403


def test_guest_active_list_requires_authentication(
    client,
):
    response = client.get(
        "/admin/guest-sessions/active",
    )

    assert response.status_code == 401


def test_guest_active_query_is_read_only(
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

    result = start_guest_session(
        db_session,
        station_id=station.id,
        authorized_seconds=3600,
    )

    session = db_session.get(
        UsageSession,
        result.session_id,
    )

    assert session is not None

    session_before = (
        session.status,
        session.authorized_seconds,
        session.started_at,
        session.ended_at,
        session.consumed_seconds,
    )

    transaction_count_before = _count_rows(
        db_session,
        TimeTransaction,
    )

    response = client.get(
        "/admin/guest-sessions/active",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    db_session.expire_all()

    stored_session = db_session.get(
        UsageSession,
        result.session_id,
    )

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_session is not None
    assert stored_station is not None

    assert (
        stored_session.status,
        stored_session.authorized_seconds,
        stored_session.started_at,
        stored_session.ended_at,
        stored_session.consumed_seconds,
    ) == session_before

    assert stored_station.status == "IN_USE"

    assert _count_rows(
        db_session,
        TimeTransaction,
    ) == transaction_count_before


def test_multiple_guests_can_be_active_on_different_stations(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    station_one = _create_station(
        db_session,
        code="PC-01",
    )

    station_two = _create_station(
        db_session,
        code="PC-02",
    )

    first = start_guest_session(
        db_session,
        station_id=station_one.id,
        authorized_seconds=1800,
    )

    second = start_guest_session(
        db_session,
        station_id=station_two.id,
        authorized_seconds=3600,
    )

    response = client.get(
        "/admin/guest-sessions/active",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    assert {
        item["session_id"]
        for item in data
    } == {
        str(first.session_id),
        str(second.session_id),
    }


def test_admin_can_finish_guest_session(
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

    result = start_guest_session(
        db_session,
        station_id=station.id,
        authorized_seconds=3600,
    )

    usage_session = db_session.get(
        UsageSession,
        result.session_id,
    )

    assert usage_session is not None

    _move_session_into_past(
        db_session,
        usage_session,
        seconds=900,
    )

    response = client.post(
        (
            f"/admin/guest-sessions/"
            f"{result.session_id}/finish"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["session_id"] == str(
        result.session_id
    )
    assert data["station_id"] == str(
        station.id
    )

    assert data["authorized_seconds"] == 3600

    consumed = data["consumed_seconds"]

    assert 900 <= consumed <= 905

    assert (
        data["unused_seconds"]
        == 3600 - consumed
    )

    assert data["session_type"] == "GUEST"
    assert data["session_status"] == "FINISHED"
    assert data["station_status"] == "AVAILABLE"

    db_session.expire_all()

    stored_session = db_session.get(
        UsageSession,
        result.session_id,
    )

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_session is not None
    assert stored_station is not None

    assert stored_session.status == "FINISHED"
    assert (
        stored_session.consumed_seconds
        == consumed
    )
    assert stored_session.ended_at is not None

    assert stored_station.status == "AVAILABLE"


def test_finished_guest_does_not_create_wallet_or_ledger_entries(
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

    wallets_before = _count_rows(
        db_session,
        TimeWallet,
    )

    transactions_before = _count_rows(
        db_session,
        TimeTransaction,
    )

    result = start_guest_session(
        db_session,
        station_id=station.id,
        authorized_seconds=1800,
    )

    response = client.post(
        (
            f"/admin/guest-sessions/"
            f"{result.session_id}/finish"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    assert _count_rows(
        db_session,
        TimeWallet,
    ) == wallets_before

    assert _count_rows(
        db_session,
        TimeTransaction,
    ) == transactions_before


def test_guest_finish_caps_consumption_at_authorized_time(
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

    result = start_guest_session(
        db_session,
        station_id=station.id,
        authorized_seconds=60,
    )

    session = db_session.get(
        UsageSession,
        result.session_id,
    )

    assert session is not None

    _move_session_into_past(
        db_session,
        session,
        seconds=120,
    )

    response = client.post(
        (
            f"/admin/guest-sessions/"
            f"{result.session_id}/finish"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["consumed_seconds"] == 60
    assert data["unused_seconds"] == 0


def test_finished_guest_cannot_be_finished_twice(
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

    result = start_guest_session(
        db_session,
        station_id=station.id,
        authorized_seconds=1800,
    )

    first = client.post(
        (
            f"/admin/guest-sessions/"
            f"{result.session_id}/finish"
        ),
        headers=auth_headers(admin),
    )

    assert first.status_code == 200

    second = client.post(
        (
            f"/admin/guest-sessions/"
            f"{result.session_id}/finish"
        ),
        headers=auth_headers(admin),
    )

    assert second.status_code == 409

    assert second.json() == {
        "detail": (
            "Guest session is already finished"
        )
    }


def test_unknown_guest_finish_returns_404(
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
            f"/admin/guest-sessions/"
            f"{uuid4()}/finish"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 404


def test_customer_cannot_finish_guest_session(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    customer = user_factory(
        username="cliente01",
    )

    station = _create_station(
        db_session,
    )

    result = start_guest_session(
        db_session,
        station_id=station.id,
        authorized_seconds=1800,
    )

    response = client.post(
        (
            f"/admin/guest-sessions/"
            f"{result.session_id}/finish"
        ),
        headers=auth_headers(customer),
    )

    assert response.status_code == 403


def test_guest_finish_requires_authentication(
    client,
    db_session,
):
    station = _create_station(
        db_session,
    )

    result = start_guest_session(
        db_session,
        station_id=station.id,
        authorized_seconds=1800,
    )

    response = client.post(
        (
            f"/admin/guest-sessions/"
            f"{result.session_id}/finish"
        ),
    )

    assert response.status_code == 401


def test_guest_session_cannot_be_finished_by_registered_endpoint(
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

    guest = start_guest_session(
        db_session,
        station_id=station.id,
        authorized_seconds=1800,
    )

    transactions_before = _count_rows(
        db_session,
        TimeTransaction,
    )

    response = client.post(
        (
            f"/admin/sessions/"
            f"{guest.session_id}/finish"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 404

    db_session.expire_all()

    stored_guest = db_session.get(
        UsageSession,
        guest.session_id,
    )

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_guest is not None
    assert stored_station is not None

    assert stored_guest.status == "ACTIVE"
    assert stored_guest.session_type == "GUEST"
    assert stored_station.status == "IN_USE"

    assert _count_rows(
        db_session,
        TimeTransaction,
    ) == transactions_before


def test_guest_session_cannot_be_extended_by_registered_endpoint(
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

    guest = start_guest_session(
        db_session,
        station_id=station.id,
        authorized_seconds=1800,
    )

    response = client.post(
        (
            f"/admin/sessions/"
            f"{guest.session_id}/extend"
        ),
        json={
            "additional_seconds": 600,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 404

    db_session.expire_all()

    stored_guest = db_session.get(
        UsageSession,
        guest.session_id,
    )

    assert stored_guest is not None
    assert stored_guest.authorized_seconds == 1800


def test_registered_session_cannot_be_finished_by_guest_endpoint(
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

    registered = (
        start_registered_customer_session(
            db_session,
            station_id=station.id,
            customer_id=customer.id,
            authorized_seconds=1800,
            actor_user_id=admin.id,
        )
    )

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    balances_before = (
        wallet.available_seconds,
        wallet.reserved_seconds,
    )

    response = client.post(
        (
            f"/admin/guest-sessions/"
            f"{registered.session_id}/finish"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 404

    db_session.expire_all()

    stored_session = db_session.get(
        UsageSession,
        registered.session_id,
    )

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    assert stored_session is not None
    assert stored_session.status == "ACTIVE"
    assert (
        stored_session.session_type
        == "REGISTERED"
    )

    assert (
        wallet.available_seconds,
        wallet.reserved_seconds,
    ) == balances_before


def test_guest_does_not_appear_in_registered_active_endpoint(
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

    start_guest_session(
        db_session,
        station_id=station.id,
        authorized_seconds=1800,
    )

    response = client.get(
        "/admin/sessions/active",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json() == []


def test_registered_session_does_not_appear_in_guest_active_endpoint(
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

    start_registered_customer_session(
        db_session,
        station_id=station.id,
        customer_id=customer.id,
        authorized_seconds=1800,
        actor_user_id=admin.id,
    )

    response = client.get(
        "/admin/guest-sessions/active",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json() == []


def test_finished_guest_does_not_appear_in_registered_history(
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

    guest = start_guest_session(
        db_session,
        station_id=station.id,
        authorized_seconds=1800,
    )

    finish_guest_session(
        db_session,
        session_id=guest.session_id,
    )

    response = client.get(
        "/admin/sessions/history",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json() == []


def test_guest_start_rolls_back_if_database_flush_fails(
    db_session,
    monkeypatch,
):
    station = _create_station(
        db_session,
    )

    original_flush = db_session.flush

    def fail_flush(*args, **kwargs):
        raise IntegrityError(
            "forced guest start failure",
            {},
            Exception("forced failure"),
        )

    monkeypatch.setattr(
        db_session,
        "flush",
        fail_flush,
    )

    with pytest.raises(
        GuestSessionStartConflictError
    ):
        start_guest_session(
            db_session,
            station_id=station.id,
            authorized_seconds=1800,
        )

    monkeypatch.setattr(
        db_session,
        "flush",
        original_flush,
    )

    db_session.expire_all()

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_station is not None
    assert stored_station.status == "AVAILABLE"

    sessions = db_session.scalars(
        select(UsageSession).where(
            UsageSession.station_id
            == station.id
        )
    ).all()

    assert sessions == []


def test_guest_finish_rolls_back_if_database_flush_fails(
    db_session,
    monkeypatch,
):
    station = _create_station(
        db_session,
    )

    guest = start_guest_session(
        db_session,
        station_id=station.id,
        authorized_seconds=1800,
    )

    original_flush = db_session.flush

    def fail_flush(*args, **kwargs):
        raise IntegrityError(
            "forced guest finish failure",
            {},
            Exception("forced failure"),
        )

    monkeypatch.setattr(
        db_session,
        "flush",
        fail_flush,
    )

    with pytest.raises(
        GuestSessionFinishConflictError
    ):
        finish_guest_session(
            db_session,
            session_id=guest.session_id,
        )

    monkeypatch.setattr(
        db_session,
        "flush",
        original_flush,
    )

    db_session.expire_all()

    stored_session = db_session.get(
        UsageSession,
        guest.session_id,
    )

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_session is not None
    assert stored_station is not None

    assert stored_session.status == "ACTIVE"
    assert stored_session.ended_at is None
    assert stored_session.consumed_seconds is None

    assert stored_station.status == "IN_USE"


def test_station_maintenance_wins_race_against_guest_start(
    db_session,
):
    station = _create_station(
        db_session,
    )

    bind = db_session.get_bind()

    status_db = Session(
        bind=bind,
        autoflush=False,
        expire_on_commit=False,
    )

    guest_db = Session(
        bind=bind,
        autoflush=False,
        expire_on_commit=False,
    )

    status_has_lock = Event()
    allow_status = Event()
    guest_attempted_lock = Event()

    status_result = {}
    guest_errors = []

    def after_cursor_execute(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        role = conn.info.get(
            "guest_race_role"
        )

        normalized = " ".join(
            statement.upper().split()
        )

        if (
            role == "status"
            and "FOR UPDATE" in normalized
            and "STATIONS" in normalized
        ):
            status_has_lock.set()

            if not allow_status.wait(
                timeout=5
            ):
                raise RuntimeError(
                    "Timed out releasing status lock"
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
            "guest_race_role"
        )

        normalized = " ".join(
            statement.upper().split()
        )

        if (
            role == "guest"
            and "FOR UPDATE" in normalized
            and "STATIONS" in normalized
        ):
            guest_attempted_lock.set()

    def run_status():
        try:
            connection = status_db.connection()
            connection.info[
                "guest_race_role"
            ] = "status"

            status_result["value"] = (
                update_station_status(
                    status_db,
                    station_id=station.id,
                    status="MAINTENANCE",
                )
            )
        except Exception as exc:
            status_result["error"] = exc

    def run_guest():
        try:
            connection = guest_db.connection()
            connection.info[
                "guest_race_role"
            ] = "guest"

            start_guest_session(
                guest_db,
                station_id=station.id,
                authorized_seconds=1800,
            )
        except Exception as exc:
            guest_errors.append(exc)

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

    status_thread = Thread(
        target=run_status,
        daemon=True,
    )

    guest_thread = Thread(
        target=run_guest,
        daemon=True,
    )

    try:
        status_thread.start()

        assert status_has_lock.wait(
            timeout=5
        )

        guest_thread.start()

        assert guest_attempted_lock.wait(
            timeout=5
        )

        assert guest_thread.is_alive()

        allow_status.set()

        status_thread.join(timeout=10)
        guest_thread.join(timeout=10)

    finally:
        allow_status.set()

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

        status_thread.join(timeout=1)
        guest_thread.join(timeout=1)

        if not status_thread.is_alive():
            status_db.close()

        if not guest_thread.is_alive():
            guest_db.close()

    assert not status_thread.is_alive()
    assert not guest_thread.is_alive()

    assert "error" not in status_result

    assert len(guest_errors) == 1
    assert isinstance(
        guest_errors[0],
        SessionStationUnavailableError,
    )

    db_session.expire_all()

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_station is not None
    assert stored_station.status == "MAINTENANCE"

    active_sessions = db_session.scalars(
        select(UsageSession).where(
            UsageSession.station_id
            == station.id,
            UsageSession.status
            == "ACTIVE",
        )
    ).all()

    assert active_sessions == []


def test_guest_start_wins_race_against_station_maintenance(
    db_session,
):
    station = _create_station(
        db_session,
    )

    bind = db_session.get_bind()

    guest_db = Session(
        bind=bind,
        autoflush=False,
        expire_on_commit=False,
    )

    status_db = Session(
        bind=bind,
        autoflush=False,
        expire_on_commit=False,
    )

    guest_has_lock = Event()
    allow_guest = Event()
    status_attempted_lock = Event()

    guest_result = {}
    status_errors = []

    def after_cursor_execute(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        role = conn.info.get(
            "guest_start_race_role"
        )

        normalized = " ".join(
            statement.upper().split()
        )

        if (
            role == "guest"
            and "FOR UPDATE" in normalized
            and "STATIONS" in normalized
        ):
            guest_has_lock.set()

            if not allow_guest.wait(
                timeout=5
            ):
                raise RuntimeError(
                    "Timed out releasing guest lock"
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
            "guest_start_race_role"
        )

        normalized = " ".join(
            statement.upper().split()
        )

        if (
            role == "status"
            and "FOR UPDATE" in normalized
            and "STATIONS" in normalized
        ):
            status_attempted_lock.set()

    def run_guest():
        try:
            connection = guest_db.connection()
            connection.info[
                "guest_start_race_role"
            ] = "guest"

            guest_result["value"] = (
                start_guest_session(
                    guest_db,
                    station_id=station.id,
                    authorized_seconds=1800,
                )
            )
        except Exception as exc:
            guest_result["error"] = exc

    def run_status():
        try:
            connection = status_db.connection()
            connection.info[
                "guest_start_race_role"
            ] = "status"

            update_station_status(
                status_db,
                station_id=station.id,
                status="MAINTENANCE",
            )
        except Exception as exc:
            status_errors.append(exc)

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

    guest_thread = Thread(
        target=run_guest,
        daemon=True,
    )

    status_thread = Thread(
        target=run_status,
        daemon=True,
    )

    try:
        guest_thread.start()

        assert guest_has_lock.wait(
            timeout=5
        )

        status_thread.start()

        assert status_attempted_lock.wait(
            timeout=5
        )

        assert status_thread.is_alive()

        allow_guest.set()

        guest_thread.join(timeout=10)
        status_thread.join(timeout=10)

    finally:
        allow_guest.set()

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

        guest_thread.join(timeout=1)
        status_thread.join(timeout=1)

        if not guest_thread.is_alive():
            guest_db.close()

        if not status_thread.is_alive():
            status_db.close()

    assert not guest_thread.is_alive()
    assert not status_thread.is_alive()

    assert "error" not in guest_result

    assert len(status_errors) == 1
    assert isinstance(
        status_errors[0],
        StationInUseError,
    )

    db_session.expire_all()

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_station is not None
    assert stored_station.status == "IN_USE"

    active_sessions = db_session.scalars(
        select(UsageSession).where(
            UsageSession.station_id
            == station.id,
            UsageSession.status
            == "ACTIVE",
        )
    ).all()

    assert len(active_sessions) == 1

    assert (
        active_sessions[0].session_type
        == "GUEST"
    )