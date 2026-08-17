from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.models.station import Station
from app.models.time_transaction import TimeTransaction
from app.models.time_wallet import TimeWallet
from app.models.usage_session import UsageSession
from app.models.user import User


def _create_station(
    db_session,
    *,
    code: str,
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


def _create_finished_guest_session(
    db_session,
    *,
    station: Station,
    authorized_seconds: int = 3600,
    consumed_seconds: int = 2400,
    started_at: datetime,
    ended_at: datetime,
    session_id: UUID | None = None,
) -> UsageSession:
    session = UsageSession(
        id=session_id or uuid4(),
        station_id=station.id,
        user_id=None,
        session_type="GUEST",
        status="FINISHED",
        authorized_seconds=authorized_seconds,
        consumed_seconds=consumed_seconds,
        started_at=started_at,
        ended_at=ended_at,
    )

    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    return session


def _create_active_guest_session(
    db_session,
    *,
    station: Station,
    authorized_seconds: int = 3600,
    started_at: datetime,
) -> UsageSession:
    session = UsageSession(
        station_id=station.id,
        user_id=None,
        session_type="GUEST",
        status="ACTIVE",
        authorized_seconds=authorized_seconds,
        consumed_seconds=None,
        started_at=started_at,
        ended_at=None,
    )

    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    return session


def _create_finished_registered_session(
    db_session,
    *,
    station: Station,
    customer,
    started_at: datetime,
    ended_at: datetime,
) -> UsageSession:
    session = UsageSession(
        station_id=station.id,
        user_id=customer.id,
        session_type="REGISTERED",
        status="FINISHED",
        authorized_seconds=3600,
        consumed_seconds=1800,
        started_at=started_at,
        ended_at=ended_at,
    )

    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    return session


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


def test_admin_can_list_finished_guest_session_history(
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
        code="PC-01",
    )

    session = _create_finished_guest_session(
        db_session,
        station=station,
        authorized_seconds=7200,
        consumed_seconds=4800,
        started_at=datetime(
            2026,
            8,
            16,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        ended_at=datetime(
            2026,
            8,
            16,
            11,
            20,
            tzinfo=timezone.utc,
        ),
    )

    response = client.get(
        "/admin/guest-sessions/history",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    item = data[0]

    assert item["session_id"] == str(
        session.id
    )
    assert item["station_id"] == str(
        station.id
    )
    assert item["station_code"] == "PC-01"

    assert item["authorized_seconds"] == 7200
    assert item["consumed_seconds"] == 4800
    assert item["unused_seconds"] == 2400

    assert item["started_at"] is not None
    assert item["ended_at"] is not None

    assert set(item.keys()) == {
        "session_id",
        "station_id",
        "station_code",
        "authorized_seconds",
        "consumed_seconds",
        "unused_seconds",
        "started_at",
        "ended_at",
    }


def test_guest_session_history_requires_admin(
    client,
    user_factory,
    auth_headers,
):
    customer = user_factory(
        username="cliente01",
    )

    response = client.get(
        "/admin/guest-sessions/history",
        headers=auth_headers(customer),
    )

    assert response.status_code == 403


def test_guest_session_history_requires_authentication(
    client,
):
    response = client.get(
        "/admin/guest-sessions/history"
    )

    assert response.status_code == 401


def test_guest_session_history_excludes_active_and_registered_sessions(
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

    finished_guest_station = _create_station(
        db_session,
        code="PC-01",
    )

    active_guest_station = _create_station(
        db_session,
        code="PC-02",
        status="IN_USE",
    )

    registered_station = _create_station(
        db_session,
        code="PC-03",
    )

    started_at = datetime(
        2026,
        8,
        16,
        10,
        0,
        tzinfo=timezone.utc,
    )

    finished_guest = (
        _create_finished_guest_session(
            db_session,
            station=finished_guest_station,
            started_at=started_at,
            ended_at=datetime(
                2026,
                8,
                16,
                11,
                0,
                tzinfo=timezone.utc,
            ),
        )
    )

    active_guest = _create_active_guest_session(
        db_session,
        station=active_guest_station,
        started_at=started_at,
    )

    registered = (
        _create_finished_registered_session(
            db_session,
            station=registered_station,
            customer=customer,
            started_at=started_at,
            ended_at=datetime(
                2026,
                8,
                16,
                12,
                0,
                tzinfo=timezone.utc,
            ),
        )
    )

    response = client.get(
        "/admin/guest-sessions/history",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    ids = {
        item["session_id"]
        for item in response.json()
    }

    assert str(finished_guest.id) in ids
    assert str(active_guest.id) not in ids
    assert str(registered.id) not in ids


def test_guest_history_keeps_non_available_station(
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
        code="PC-01",
        status="MAINTENANCE",
    )

    session = _create_finished_guest_session(
        db_session,
        station=station,
        started_at=datetime(
            2026,
            8,
            16,
            9,
            0,
            tzinfo=timezone.utc,
        ),
        ended_at=datetime(
            2026,
            8,
            16,
            10,
            0,
            tzinfo=timezone.utc,
        ),
    )

    response = client.get(
        "/admin/guest-sessions/history",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    assert [
        item["session_id"]
        for item in response.json()
    ] == [
        str(session.id)
    ]


def test_guest_session_history_filters_by_station(
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

    target = _create_finished_guest_session(
        db_session,
        station=station_one,
        started_at=datetime(
            2026,
            8,
            16,
            9,
            0,
            tzinfo=timezone.utc,
        ),
        ended_at=datetime(
            2026,
            8,
            16,
            10,
            0,
            tzinfo=timezone.utc,
        ),
    )

    _create_finished_guest_session(
        db_session,
        station=station_two,
        started_at=datetime(
            2026,
            8,
            16,
            11,
            0,
            tzinfo=timezone.utc,
        ),
        ended_at=datetime(
            2026,
            8,
            16,
            12,
            0,
            tzinfo=timezone.utc,
        ),
    )

    response = client.get(
        "/admin/guest-sessions/history",
        params={
            "station_id": str(
                station_one.id
            ),
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    assert [
        item["session_id"]
        for item in response.json()
    ] == [
        str(target.id)
    ]


def test_guest_session_history_unknown_station_returns_empty_list(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.get(
        "/admin/guest-sessions/history",
        params={
            "station_id": str(uuid4()),
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json() == []


def test_guest_session_history_has_deterministic_descending_order(
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
        code="PC-01",
    )

    older_end = datetime(
        2026,
        8,
        16,
        10,
        0,
        tzinfo=timezone.utc,
    )

    newer_end = datetime(
        2026,
        8,
        16,
        12,
        0,
        tzinfo=timezone.utc,
    )

    older = _create_finished_guest_session(
        db_session,
        station=station,
        session_id=UUID(
            "00000000-0000-0000-0000-000000000001"
        ),
        started_at=datetime(
            2026,
            8,
            16,
            9,
            0,
            tzinfo=timezone.utc,
        ),
        ended_at=older_end,
    )

    newer_low_id = (
        _create_finished_guest_session(
            db_session,
            station=station,
            session_id=UUID(
                "00000000-0000-0000-0000-000000000002"
            ),
            started_at=datetime(
                2026,
                8,
                16,
                11,
                0,
                tzinfo=timezone.utc,
            ),
            ended_at=newer_end,
        )
    )

    newer_high_id = (
        _create_finished_guest_session(
            db_session,
            station=station,
            session_id=UUID(
                "00000000-0000-0000-0000-000000000003"
            ),
            started_at=datetime(
                2026,
                8,
                16,
                11,
                10,
                tzinfo=timezone.utc,
            ),
            ended_at=newer_end,
        )
    )

    response = client.get(
        "/admin/guest-sessions/history",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    ids = [
        item["session_id"]
        for item in response.json()
    ]

    assert ids == [
        str(newer_high_id.id),
        str(newer_low_id.id),
        str(older.id),
    ]


def test_guest_session_history_supports_pagination(
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
        code="PC-01",
    )

    ended_at = datetime(
        2026,
        8,
        16,
        12,
        0,
        tzinfo=timezone.utc,
    )

    sessions = []

    for index in range(1, 5):
        sessions.append(
            _create_finished_guest_session(
                db_session,
                station=station,
                session_id=UUID(
                    (
                        "00000000-0000-0000-0000-"
                        f"{index:012d}"
                    )
                ),
                started_at=datetime(
                    2026,
                    8,
                    16,
                    10,
                    0,
                    tzinfo=timezone.utc,
                ),
                ended_at=ended_at,
            )
        )

    response = client.get(
        "/admin/guest-sessions/history",
        params={
            "limit": 2,
            "offset": 1,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    ids = [
        item["session_id"]
        for item in response.json()
    ]

    assert ids == [
        str(sessions[2].id),
        str(sessions[1].id),
    ]


@pytest.mark.parametrize(
    "params",
    [
        {
            "limit": 0,
        },
        {
            "limit": 101,
        },
        {
            "offset": -1,
        },
    ],
)
def test_guest_session_history_rejects_invalid_pagination(
    client,
    user_factory,
    auth_headers,
    params,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.get(
        "/admin/guest-sessions/history",
        params=params,
        headers=auth_headers(admin),
    )

    assert response.status_code == 422


def test_guest_session_history_is_strictly_read_only(
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
        available_seconds=5400,
        reserved_seconds=0,
    )

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    transaction = TimeTransaction(
        wallet_id=wallet.id,
        transaction_type="PURCHASE",
        available_seconds_delta=5400,
        reserved_seconds_delta=0,
        actor_user_id=admin.id,
    )

    db_session.add(transaction)
    db_session.commit()
    db_session.refresh(transaction)

    station = _create_station(
        db_session,
        code="PC-01",
        status="MAINTENANCE",
    )

    session = _create_finished_guest_session(
        db_session,
        station=station,
        authorized_seconds=3600,
        consumed_seconds=2400,
        started_at=datetime(
            2026,
            8,
            16,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        ended_at=datetime(
            2026,
            8,
            16,
            10,
            40,
            tzinfo=timezone.utc,
        ),
    )

    session_before = (
        session.station_id,
        session.user_id,
        session.session_type,
        session.status,
        session.authorized_seconds,
        session.consumed_seconds,
        session.started_at,
        session.ended_at,
    )

    station_before = (
        station.code,
        station.status,
        station.updated_at,
    )

    wallet_before = (
        wallet.available_seconds,
        wallet.reserved_seconds,
        wallet.updated_at,
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

    response = client.get(
        "/admin/guest-sessions/history",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    db_session.expire_all()

    stored_session = db_session.get(
        UsageSession,
        session.id,
    )
    stored_station = db_session.get(
        Station,
        station.id,
    )
    stored_wallet = db_session.get(
        TimeWallet,
        wallet.id,
    )

    assert stored_session is not None
    assert stored_station is not None
    assert stored_wallet is not None

    session_after = (
        stored_session.station_id,
        stored_session.user_id,
        stored_session.session_type,
        stored_session.status,
        stored_session.authorized_seconds,
        stored_session.consumed_seconds,
        stored_session.started_at,
        stored_session.ended_at,
    )

    station_after = (
        stored_station.code,
        stored_station.status,
        stored_station.updated_at,
    )

    wallet_after = (
        stored_wallet.available_seconds,
        stored_wallet.reserved_seconds,
        stored_wallet.updated_at,
    )

    assert session_after == session_before
    assert station_after == station_before
    assert wallet_after == wallet_before

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