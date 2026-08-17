from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select

from app.models.station import Station
from app.models.time_transaction import (
    TimeTransaction,
)
from app.models.time_wallet import TimeWallet
from app.models.usage_session import UsageSession
from app.models.user import User


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


def test_admin_can_get_customer_detail(
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
        display_name="Juan Perez",
        available_seconds=7200,
        reserved_seconds=1800,
    )

    response = client.get(
        (
            f"/admin/customers/"
            f"{customer.id}"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == str(customer.id)
    assert data["username"] == "cliente01"
    assert data["display_name"] == "Juan Perez"
    assert data["is_active"] is True

    assert data["created_at"] is not None
    assert data["updated_at"] is not None

    assert data["available_seconds"] == 7200
    assert data["reserved_seconds"] == 1800

    assert set(data.keys()) == {
        "id",
        "username",
        "display_name",
        "is_active",
        "created_at",
        "updated_at",
        "available_seconds",
        "reserved_seconds",
    }


def test_customer_cannot_get_admin_customer_detail(
    client,
    user_factory,
    auth_headers,
):
    requester = user_factory(
        username="cliente01",
    )

    target = user_factory(
        username="cliente02",
    )

    response = client.get(
        (
            f"/admin/customers/"
            f"{target.id}"
        ),
        headers=auth_headers(requester),
    )

    assert response.status_code == 403


def test_admin_customer_detail_requires_authentication(
    client,
):
    response = client.get(
        (
            f"/admin/customers/"
            f"{uuid4()}"
        )
    )

    assert response.status_code == 401


def test_admin_customer_detail_returns_404_for_missing_customer(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.get(
        (
            f"/admin/customers/"
            f"{uuid4()}"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Customer not found",
    }


def test_admin_uuid_is_not_customer_detail(
    client,
    user_factory,
    auth_headers,
):
    requester = user_factory(
        username="admin01",
        role="ADMIN",
    )

    other_admin = user_factory(
        username="admin02",
        role="ADMIN",
    )

    response = client.get(
        (
            f"/admin/customers/"
            f"{other_admin.id}"
        ),
        headers=auth_headers(requester),
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Customer not found",
    }


def test_admin_can_get_inactive_customer_detail(
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
        display_name="Cliente Inactivo",
        is_active=False,
        available_seconds=3600,
        reserved_seconds=0,
    )

    response = client.get(
        (
            f"/admin/customers/"
            f"{customer.id}"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == str(customer.id)
    assert data["is_active"] is False
    assert data["available_seconds"] == 3600
    assert data["reserved_seconds"] == 0


def test_admin_customer_detail_reports_missing_wallet(
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

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    db_session.delete(wallet)
    db_session.commit()

    response = client.get(
        (
            f"/admin/customers/"
            f"{customer.id}"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 409

    assert response.json() == {
        "detail": "Customer wallet not found",
    }


def test_admin_customer_detail_is_strictly_read_only(
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
        display_name="Cliente Prueba",
        available_seconds=5400,
        reserved_seconds=1800,
    )

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    station = Station(
        code="PC-01",
        status="MAINTENANCE",
    )

    db_session.add(station)
    db_session.commit()
    db_session.refresh(station)

    usage_session = UsageSession(
        station_id=station.id,
        user_id=customer.id,
        session_type="REGISTERED",
        status="FINISHED",
        authorized_seconds=1800,
        consumed_seconds=1200,
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
            20,
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

    db_session.add_all(
        [
            usage_session,
            transaction,
        ]
    )
    db_session.commit()

    db_session.refresh(usage_session)
    db_session.refresh(transaction)

    customer_before = (
        customer.username,
        customer.display_name,
        customer.is_active,
        customer.created_at,
        customer.updated_at,
    )

    wallet_before = (
        wallet.available_seconds,
        wallet.reserved_seconds,
        wallet.updated_at,
    )

    session_before = (
        usage_session.station_id,
        usage_session.user_id,
        usage_session.session_type,
        usage_session.status,
        usage_session.authorized_seconds,
        usage_session.consumed_seconds,
        usage_session.started_at,
        usage_session.ended_at,
    )

    users_before = db_session.scalar(
        select(func.count())
        .select_from(User)
    )

    wallets_before = db_session.scalar(
        select(func.count())
        .select_from(TimeWallet)
    )

    sessions_before = db_session.scalar(
        select(func.count())
        .select_from(UsageSession)
    )

    transactions_before = db_session.scalar(
        select(func.count())
        .select_from(TimeTransaction)
    )

    response = client.get(
        (
            f"/admin/customers/"
            f"{customer.id}"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    db_session.expire_all()

    stored_customer = db_session.get(
        User,
        customer.id,
    )

    stored_wallet = db_session.get(
        TimeWallet,
        wallet.id,
    )

    stored_session = db_session.get(
        UsageSession,
        usage_session.id,
    )

    assert stored_customer is not None
    assert stored_wallet is not None
    assert stored_session is not None

    customer_after = (
        stored_customer.username,
        stored_customer.display_name,
        stored_customer.is_active,
        stored_customer.created_at,
        stored_customer.updated_at,
    )

    wallet_after = (
        stored_wallet.available_seconds,
        stored_wallet.reserved_seconds,
        stored_wallet.updated_at,
    )

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

    users_after = db_session.scalar(
        select(func.count())
        .select_from(User)
    )

    wallets_after = db_session.scalar(
        select(func.count())
        .select_from(TimeWallet)
    )

    sessions_after = db_session.scalar(
        select(func.count())
        .select_from(UsageSession)
    )

    transactions_after = db_session.scalar(
        select(func.count())
        .select_from(TimeTransaction)
    )

    assert customer_after == customer_before
    assert wallet_after == wallet_before
    assert session_after == session_before

    assert users_after == users_before
    assert wallets_after == wallets_before
    assert sessions_after == sessions_before

    assert (
        transactions_after
        == transactions_before
    )