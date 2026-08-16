from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.models.station import Station
from app.models.time_transaction import TimeTransaction
from app.models.time_wallet import TimeWallet
from app.models.usage_session import UsageSession


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


def _create_finished_session(
    db_session,
    *,
    station: Station,
    customer,
    authorized_seconds: int = 3600,
    consumed_seconds: int = 2400,
    started_at: datetime,
    ended_at: datetime,
    session_id: UUID | None = None,
) -> UsageSession:
    session = UsageSession(
        id=session_id or uuid4(),
        station_id=station.id,
        user_id=customer.id,
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


def _create_active_session(
    db_session,
    *,
    station: Station,
    customer,
    authorized_seconds: int = 3600,
    started_at: datetime,
) -> UsageSession:
    session = UsageSession(
        station_id=station.id,
        user_id=customer.id,
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


def test_admin_can_list_finished_session_history(
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
        display_name="Juan Perez",
    )

    station = _create_station(
        db_session,
        code="PC-01",
    )

    started_at = datetime(
        2026,
        8,
        16,
        10,
        0,
        tzinfo=timezone.utc,
    )

    ended_at = datetime(
        2026,
        8,
        16,
        11,
        20,
        tzinfo=timezone.utc,
    )

    session = _create_finished_session(
        db_session,
        station=station,
        customer=customer,
        authorized_seconds=7200,
        consumed_seconds=4800,
        started_at=started_at,
        ended_at=ended_at,
    )

    response = client.get(
        "/admin/sessions/history",
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

    assert item["customer_id"] == str(
        customer.id
    )
    assert (
        item["customer_username"]
        == "cliente01"
    )
    assert (
        item["customer_display_name"]
        == "Juan Perez"
    )

    assert item["authorized_seconds"] == 7200
    assert item["consumed_seconds"] == 4800
    assert item["released_seconds"] == 2400

    assert item["started_at"] is not None
    assert item["ended_at"] is not None

    assert set(item.keys()) == {
        "session_id",
        "station_id",
        "station_code",
        "customer_id",
        "customer_username",
        "customer_display_name",
        "authorized_seconds",
        "consumed_seconds",
        "released_seconds",
        "started_at",
        "ended_at",
    }


def test_session_history_requires_admin(
    client,
    user_factory,
    auth_headers,
):
    customer = user_factory(
        username="cliente01",
    )

    response = client.get(
        "/admin/sessions/history",
        headers=auth_headers(customer),
    )

    assert response.status_code == 403


def test_session_history_requires_authentication(
    client,
):
    response = client.get(
        "/admin/sessions/history"
    )

    assert response.status_code == 401


def test_session_history_excludes_active_sessions(
    client,
    db_session,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    finished_customer = user_factory(
        username="cliente01",
    )

    active_customer = user_factory(
        username="cliente02",
    )

    finished_station = _create_station(
        db_session,
        code="PC-01",
    )

    active_station = _create_station(
        db_session,
        code="PC-02",
        status="IN_USE",
    )

    started_at = datetime(
        2026,
        8,
        16,
        10,
        0,
        tzinfo=timezone.utc,
    )

    finished = _create_finished_session(
        db_session,
        station=finished_station,
        customer=finished_customer,
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

    active = _create_active_session(
        db_session,
        station=active_station,
        customer=active_customer,
        started_at=started_at,
    )

    response = client.get(
        "/admin/sessions/history",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    ids = {
        item["session_id"]
        for item in response.json()
    }

    assert str(finished.id) in ids
    assert str(active.id) not in ids


def test_history_keeps_inactive_customer_and_non_available_station(
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
    )

    station = _create_station(
        db_session,
        code="PC-01",
        status="MAINTENANCE",
    )

    session = _create_finished_session(
        db_session,
        station=station,
        customer=customer,
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
        "/admin/sessions/history",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    assert [
        item["session_id"]
        for item in response.json()
    ] == [
        str(session.id)
    ]


def test_session_history_filters_by_customer(
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
    )

    customer_two = user_factory(
        username="cliente02",
    )

    station = _create_station(
        db_session,
        code="PC-01",
    )

    first = _create_finished_session(
        db_session,
        station=station,
        customer=customer_one,
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

    _create_finished_session(
        db_session,
        station=station,
        customer=customer_two,
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
        "/admin/sessions/history",
        params={
            "customer_id": str(
                customer_one.id
            ),
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    assert [
        item["session_id"]
        for item in response.json()
    ] == [
        str(first.id)
    ]


def test_session_history_filters_by_station(
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

    station_one = _create_station(
        db_session,
        code="PC-01",
    )

    station_two = _create_station(
        db_session,
        code="PC-02",
    )

    first = _create_finished_session(
        db_session,
        station=station_one,
        customer=customer,
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

    _create_finished_session(
        db_session,
        station=station_two,
        customer=customer,
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
        "/admin/sessions/history",
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
        str(first.id)
    ]


def test_session_history_combines_customer_and_station_filters(
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
    )

    customer_two = user_factory(
        username="cliente02",
    )

    station_one = _create_station(
        db_session,
        code="PC-01",
    )

    station_two = _create_station(
        db_session,
        code="PC-02",
    )

    target = _create_finished_session(
        db_session,
        station=station_one,
        customer=customer_one,
        started_at=datetime(
            2026,
            8,
            16,
            8,
            0,
            tzinfo=timezone.utc,
        ),
        ended_at=datetime(
            2026,
            8,
            16,
            9,
            0,
            tzinfo=timezone.utc,
        ),
    )

    _create_finished_session(
        db_session,
        station=station_two,
        customer=customer_one,
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
            0,
            tzinfo=timezone.utc,
        ),
    )

    _create_finished_session(
        db_session,
        station=station_one,
        customer=customer_two,
        started_at=datetime(
            2026,
            8,
            16,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        ended_at=datetime(
            2026,
            8,
            16,
            13,
            0,
            tzinfo=timezone.utc,
        ),
    )

    response = client.get(
        "/admin/sessions/history",
        params={
            "customer_id": str(
                customer_one.id
            ),
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


def test_session_history_unknown_filter_returns_empty_list(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.get(
        "/admin/sessions/history",
        params={
            "customer_id": str(uuid4()),
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json() == []


def test_session_history_has_deterministic_descending_order(
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

    older = _create_finished_session(
        db_session,
        station=station,
        customer=customer,
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

    newer_low_id = _create_finished_session(
        db_session,
        station=station,
        customer=customer,
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

    newer_high_id = _create_finished_session(
        db_session,
        station=station,
        customer=customer,
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

    response = client.get(
        "/admin/sessions/history",
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


def test_session_history_supports_pagination(
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
            _create_finished_session(
                db_session,
                station=station,
                customer=customer,
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
        "/admin/sessions/history",
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
def test_session_history_rejects_invalid_pagination(
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
        "/admin/sessions/history",
        params=params,
        headers=auth_headers(admin),
    )

    assert response.status_code == 422


def test_session_history_is_strictly_read_only(
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

    station = _create_station(
        db_session,
        code="PC-01",
        status="MAINTENANCE",
    )

    session = _create_finished_session(
        db_session,
        station=station,
        customer=customer,
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

    session_before = (
        session.station_id,
        session.user_id,
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

    transaction_ids_before = db_session.scalars(
        select(TimeTransaction.id)
        .where(
            TimeTransaction.wallet_id
            == wallet.id
        )
        .order_by(TimeTransaction.id)
    ).all()

    transaction_count_before = db_session.scalar(
        select(func.count())
        .select_from(TimeTransaction)
        .where(
            TimeTransaction.wallet_id
            == wallet.id
        )
    )

    response = client.get(
        "/admin/sessions/history",
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

    transaction_ids_after = db_session.scalars(
        select(TimeTransaction.id)
        .where(
            TimeTransaction.wallet_id
            == wallet.id
        )
        .order_by(TimeTransaction.id)
    ).all()

    transaction_count_after = db_session.scalar(
        select(func.count())
        .select_from(TimeTransaction)
        .where(
            TimeTransaction.wallet_id
            == wallet.id
        )
    )

    assert session_after == session_before
    assert station_after == station_before
    assert wallet_after == wallet_before

    assert (
        transaction_ids_after
        == transaction_ids_before
    )

    assert (
        transaction_count_after
        == transaction_count_before
    )