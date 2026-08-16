from threading import Event, Thread
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.models.station import Station
from app.models.time_transaction import TimeTransaction
from app.models.time_wallet import TimeWallet
from app.models.usage_session import UsageSession
from app.services.station_service import (
    StationInUseError,
    update_station_status,
)
from app.services.usage_session_service import (
    SessionStationUnavailableError,
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
            TimeWallet.user_id == customer_id
        )
    )

    assert wallet is not None

    return wallet


@pytest.mark.parametrize(
    ("initial_status", "target_status"),
    [
        ("AVAILABLE", "MAINTENANCE"),
        ("MAINTENANCE", "AVAILABLE"),
        ("AVAILABLE", "OFFLINE"),
        ("OFFLINE", "AVAILABLE"),
        ("MAINTENANCE", "OFFLINE"),
        ("OFFLINE", "MAINTENANCE"),
    ],
)
def test_admin_can_change_station_operational_status(
    client,
    db_session,
    user_factory,
    auth_headers,
    initial_status,
    target_status,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    station = _create_station(
        db_session,
        status=initial_status,
    )

    response = client.patch(
        (
            f"/admin/stations/"
            f"{station.id}/status"
        ),
        json={
            "status": target_status,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == str(station.id)
    assert data["code"] == station.code
    assert data["status"] == target_status
    assert data["created_at"]
    assert data["updated_at"]

    db_session.expire_all()

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_station is not None
    assert stored_station.status == target_status


@pytest.mark.parametrize(
    "invalid_status",
    [
        "IN_USE",
        "BROKEN",
        "",
    ],
)
def test_admin_cannot_assign_non_admin_station_status(
    client,
    db_session,
    user_factory,
    auth_headers,
    invalid_status,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    station = _create_station(
        db_session,
    )

    response = client.patch(
        (
            f"/admin/stations/"
            f"{station.id}/status"
        ),
        json={
            "status": invalid_status,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 422

    db_session.expire_all()

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_station is not None
    assert stored_station.status == "AVAILABLE"


def test_unknown_station_status_update_returns_404(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.patch(
        (
            f"/admin/stations/"
            f"{uuid4()}/status"
        ),
        json={
            "status": "MAINTENANCE",
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Station not found"
    }


def test_customer_cannot_change_station_status(
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

    response = client.patch(
        (
            f"/admin/stations/"
            f"{station.id}/status"
        ),
        json={
            "status": "MAINTENANCE",
        },
        headers=auth_headers(customer),
    )

    assert response.status_code == 403


def test_station_status_update_requires_authentication(
    client,
    db_session,
):
    station = _create_station(
        db_session,
    )

    response = client.patch(
        (
            f"/admin/stations/"
            f"{station.id}/status"
        ),
        json={
            "status": "MAINTENANCE",
        },
    )

    assert response.status_code == 401


def test_station_status_update_is_idempotent(
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
        status="MAINTENANCE",
    )

    updated_at_before = station.updated_at

    bind = db_session.get_bind()

    station_update_statements = 0

    def count_station_updates(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        nonlocal station_update_statements

        normalized_statement = (
            " ".join(statement.upper().split())
        )

        if (
            normalized_statement.startswith(
                "UPDATE STATIONS"
            )
        ):
            station_update_statements += 1

    event.listen(
        bind,
        "before_cursor_execute",
        count_station_updates,
    )

    try:
        response = client.patch(
            (
                f"/admin/stations/"
                f"{station.id}/status"
            ),
            json={
                "status": "MAINTENANCE",
            },
            headers=auth_headers(admin),
        )
    finally:
        event.remove(
            bind,
            "before_cursor_execute",
            count_station_updates,
        )

    assert response.status_code == 200
    assert response.json()["status"] == "MAINTENANCE"

    assert station_update_statements == 0

    db_session.expire_all()

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_station is not None
    assert stored_station.status == "MAINTENANCE"
    assert (
        stored_station.updated_at
        == updated_at_before
    )


def test_station_marked_in_use_cannot_be_changed_manually(
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
        status="IN_USE",
    )

    response = client.patch(
        (
            f"/admin/stations/"
            f"{station.id}/status"
        ),
        json={
            "status": "MAINTENANCE",
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 409

    assert response.json() == {
        "detail": "Station is currently in use"
    }

    db_session.expire_all()

    stored_station = db_session.get(
        Station,
        station.id,
    )

    assert stored_station is not None
    assert stored_station.status == "IN_USE"


def test_active_session_blocks_status_change_even_if_station_status_is_inconsistent(
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

    usage_session = UsageSession(
        station_id=station.id,
        user_id=customer.id,
        status="ACTIVE",
        authorized_seconds=1800,
    )

    db_session.add(usage_session)
    db_session.commit()
    db_session.refresh(usage_session)

    response = client.patch(
        (
            f"/admin/stations/"
            f"{station.id}/status"
        ),
        json={
            "status": "OFFLINE",
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 409

    db_session.expire_all()

    stored_station = db_session.get(
        Station,
        station.id,
    )

    stored_session = db_session.get(
        UsageSession,
        usage_session.id,
    )

    assert stored_station is not None
    assert stored_session is not None

    assert stored_station.status == "AVAILABLE"
    assert stored_session.status == "ACTIVE"


def test_active_session_conflict_does_not_modify_wallet_ledger_or_session(
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

    start_result = (
        start_registered_customer_session(
            db_session,
            station_id=station.id,
            customer_id=customer.id,
            authorized_seconds=3600,
            actor_user_id=admin.id,
        )
    )

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    session = db_session.get(
        UsageSession,
        start_result.session_id,
    )

    assert session is not None

    wallet_before = (
        wallet.available_seconds,
        wallet.reserved_seconds,
    )

    session_before = (
        session.status,
        session.authorized_seconds,
        session.started_at,
        session.ended_at,
        session.consumed_seconds,
    )

    transaction_ids_before = db_session.scalars(
        select(TimeTransaction.id).where(
            TimeTransaction.wallet_id
            == wallet.id
        )
    ).all()

    response = client.patch(
        (
            f"/admin/stations/"
            f"{station.id}/status"
        ),
        json={
            "status": "MAINTENANCE",
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 409

    db_session.expire_all()

    stored_station = db_session.get(
        Station,
        station.id,
    )

    stored_session = db_session.get(
        UsageSession,
        session.id,
    )

    stored_wallet = _get_wallet(
        db_session,
        customer.id,
    )

    assert stored_station is not None
    assert stored_session is not None

    assert stored_station.status == "IN_USE"

    assert (
        stored_wallet.available_seconds,
        stored_wallet.reserved_seconds,
    ) == wallet_before

    assert (
        stored_session.status,
        stored_session.authorized_seconds,
        stored_session.started_at,
        stored_session.ended_at,
        stored_session.consumed_seconds,
    ) == session_before

    transaction_ids_after = db_session.scalars(
        select(TimeTransaction.id).where(
            TimeTransaction.wallet_id
            == stored_wallet.id
        )
    ).all()

    assert (
        transaction_ids_after
        == transaction_ids_before
    )
    

def test_station_status_change_serializes_with_session_start(
    db_session,
    user_factory,
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

    bind = db_session.get_bind()

    status_db = Session(
        bind=bind,
        autoflush=False,
        expire_on_commit=False,
    )

    start_db = Session(
        bind=bind,
        autoflush=False,
        expire_on_commit=False,
    )

    status_has_station_lock = Event()
    allow_status_to_continue = Event()
    start_attempted_station_lock = Event()

    status_result = {}
    start_error = []

    def after_cursor_execute(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        role = conn.info.get(
            "station_status_concurrency_role"
        )

        normalized_statement = (
            " ".join(statement.upper().split())
        )

        if (
            role == "status"
            and "FOR UPDATE"
            in normalized_statement
            and "STATIONS"
            in normalized_statement
        ):
            status_has_station_lock.set()

            if not allow_status_to_continue.wait(
                timeout=5
            ):
                raise RuntimeError(
                    "Timed out waiting to "
                    "release station status lock"
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
            "station_status_concurrency_role"
        )

        normalized_statement = (
            " ".join(statement.upper().split())
        )

        if (
            role == "start"
            and "FOR UPDATE"
            in normalized_statement
            and "STATIONS"
            in normalized_statement
        ):
            start_attempted_station_lock.set()

    def run_status_change():
        try:
            connection = status_db.connection()

            connection.info[
                "station_status_concurrency_role"
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

    def run_session_start():
        try:
            connection = start_db.connection()

            connection.info[
                "station_status_concurrency_role"
            ] = "start"

            start_registered_customer_session(
                start_db,
                station_id=station.id,
                customer_id=customer.id,
                authorized_seconds=3600,
                actor_user_id=admin.id,
            )

        except Exception as exc:
            start_error.append(exc)

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
        target=run_status_change,
        daemon=True,
    )

    start_thread = Thread(
        target=run_session_start,
        daemon=True,
    )

    try:
        status_thread.start()

        assert status_has_station_lock.wait(
            timeout=5
        )

        start_thread.start()

        assert start_attempted_station_lock.wait(
            timeout=5
        )

        # START ya pidió el lock de Station,
        # pero STATUS todavía lo conserva.
        assert start_thread.is_alive()

        allow_status_to_continue.set()

        status_thread.join(timeout=10)
        start_thread.join(timeout=10)

    finally:
        allow_status_to_continue.set()

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
        start_thread.join(timeout=1)

        if not status_thread.is_alive():
            status_db.close()

        if not start_thread.is_alive():
            start_db.close()

    assert not status_thread.is_alive()
    assert not start_thread.is_alive()

    assert "error" not in status_result

    assert (
        status_result["value"].status
        == "MAINTENANCE"
    )

    assert len(start_error) == 1
    assert isinstance(
        start_error[0],
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

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    assert wallet.available_seconds == 7200
    assert wallet.reserved_seconds == 0

    transactions = db_session.scalars(
        select(TimeTransaction).where(
            TimeTransaction.wallet_id
            == wallet.id
        )
    ).all()

    assert transactions == []
    


def test_session_start_prevents_concurrent_status_change(
    db_session,
    user_factory,
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

    bind = db_session.get_bind()

    start_db = Session(
        bind=bind,
        autoflush=False,
        expire_on_commit=False,
    )

    status_db = Session(
        bind=bind,
        autoflush=False,
        expire_on_commit=False,
    )

    start_has_station_lock = Event()
    allow_start_to_continue = Event()
    status_attempted_station_lock = Event()

    start_result = {}
    status_error = []

    def after_cursor_execute(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):
        role = conn.info.get(
            "station_start_concurrency_role"
        )

        normalized_statement = (
            " ".join(statement.upper().split())
        )

        if (
            role == "start"
            and "FOR UPDATE"
            in normalized_statement
            and "STATIONS"
            in normalized_statement
        ):
            start_has_station_lock.set()

            if not allow_start_to_continue.wait(
                timeout=5
            ):
                raise RuntimeError(
                    "Timed out waiting to "
                    "release session start lock"
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
            "station_start_concurrency_role"
        )

        normalized_statement = (
            " ".join(statement.upper().split())
        )

        if (
            role == "status"
            and "FOR UPDATE"
            in normalized_statement
            and "STATIONS"
            in normalized_statement
        ):
            status_attempted_station_lock.set()

    def run_session_start():
        try:
            connection = start_db.connection()

            connection.info[
                "station_start_concurrency_role"
            ] = "start"

            start_result["value"] = (
                start_registered_customer_session(
                    start_db,
                    station_id=station.id,
                    customer_id=customer.id,
                    authorized_seconds=3600,
                    actor_user_id=admin.id,
                )
            )

        except Exception as exc:
            start_result["error"] = exc

    def run_status_change():
        try:
            connection = status_db.connection()

            connection.info[
                "station_start_concurrency_role"
            ] = "status"

            update_station_status(
                status_db,
                station_id=station.id,
                status="MAINTENANCE",
            )

        except Exception as exc:
            status_error.append(exc)

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

    start_thread = Thread(
        target=run_session_start,
        daemon=True,
    )

    status_thread = Thread(
        target=run_status_change,
        daemon=True,
    )

    try:
        start_thread.start()

        assert start_has_station_lock.wait(
            timeout=5
        )

        status_thread.start()

        assert status_attempted_station_lock.wait(
            timeout=5
        )

        assert status_thread.is_alive()

        allow_start_to_continue.set()

        start_thread.join(timeout=10)
        status_thread.join(timeout=10)

    finally:
        allow_start_to_continue.set()

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

        start_thread.join(timeout=1)
        status_thread.join(timeout=1)

        if not start_thread.is_alive():
            start_db.close()

        if not status_thread.is_alive():
            status_db.close()

    assert not start_thread.is_alive()
    assert not status_thread.is_alive()

    assert "error" not in start_result

    assert len(status_error) == 1
    assert isinstance(
        status_error[0],
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
        active_sessions[0].id
        == start_result["value"].session_id
    )

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