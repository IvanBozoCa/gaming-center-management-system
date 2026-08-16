from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.models.time_transaction import (
    TimeTransaction,
)
from app.models.time_wallet import TimeWallet
from app.models.user import User


def _get_wallet(
    db_session,
    customer_id,
):
    wallet = db_session.scalar(
        select(TimeWallet).where(
            TimeWallet.user_id
            == customer_id
        )
    )

    assert wallet is not None

    return wallet


def test_admin_can_get_customer_wallet(
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
        reserved_seconds=1800,
    )

    response = client.get(
        (
            f"/admin/customers/"
            f"{customer.id}/wallet"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    assert response.json() == {
        "available_seconds": 7200,
        "reserved_seconds": 1800,
    }


def test_customer_cannot_get_admin_customer_wallet(
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
            f"{target.id}/wallet"
        ),
        headers=auth_headers(requester),
    )

    assert response.status_code == 403


def test_admin_customer_wallet_requires_authentication(
    client,
):
    response = client.get(
        (
            f"/admin/customers/"
            f"{uuid4()}/wallet"
        ),
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "suffix",
    [
        "wallet",
        "time-transactions",
    ],
)
def test_admin_customer_reads_return_404_for_missing_customer(
    client,
    user_factory,
    auth_headers,
    suffix,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    response = client.get(
        (
            f"/admin/customers/"
            f"{uuid4()}/{suffix}"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Customer not found",
    }


@pytest.mark.parametrize(
    "suffix",
    [
        "wallet",
        "time-transactions",
    ],
)
def test_admin_uuid_is_not_treated_as_customer(
    client,
    user_factory,
    auth_headers,
    suffix,
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
            f"{other_admin.id}/{suffix}"
        ),
        headers=auth_headers(requester),
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Customer not found",
    }


@pytest.mark.parametrize(
    "suffix",
    [
        "wallet",
        "time-transactions",
    ],
)
def test_admin_customer_reads_report_missing_wallet(
    client,
    db_session,
    user_factory,
    auth_headers,
    suffix,
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
            f"{customer.id}/{suffix}"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 409

    assert response.json() == {
        "detail": "Customer wallet not found",
    }


def test_admin_can_get_empty_customer_time_history(
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

    response = client.get(
        (
            f"/admin/customers/"
            f"{customer.id}/time-transactions"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json() == []


def test_admin_can_get_customer_time_transaction_history(
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
        reserved_seconds=0,
    )

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    transaction = TimeTransaction(
        wallet_id=wallet.id,
        transaction_type="PURCHASE",
        available_seconds_delta=3600,
        reserved_seconds_delta=0,
        actor_user_id=admin.id,
    )

    db_session.add(transaction)
    db_session.commit()
    db_session.refresh(transaction)

    response = client.get(
        (
            f"/admin/customers/"
            f"{customer.id}/time-transactions"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    assert data[0]["id"] == str(
        transaction.id
    )

    assert (
        data[0]["transaction_type"]
        == "PURCHASE"
    )

    assert (
        data[0]["available_seconds_delta"]
        == 3600
    )

    assert (
        data[0]["reserved_seconds_delta"]
        == 0
    )

    assert data[0]["actor_user_id"] == str(
        admin.id
    )

    assert data[0]["created_at"] is not None

    assert set(data[0]) == {
        "id",
        "transaction_type",
        "available_seconds_delta",
        "reserved_seconds_delta",
        "actor_user_id",
        "created_at",
    }


def test_admin_time_history_uses_deterministic_descending_order(
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

    older_time = datetime(
        2026,
        8,
        16,
        10,
        0,
        tzinfo=timezone.utc,
    )

    newer_time = datetime(
        2026,
        8,
        16,
        11,
        0,
        tzinfo=timezone.utc,
    )

    older = TimeTransaction(
        id=UUID(
            "00000000-0000-0000-0000-000000000001"
        ),
        wallet_id=wallet.id,
        transaction_type="PURCHASE",
        available_seconds_delta=3600,
        reserved_seconds_delta=0,
        actor_user_id=admin.id,
        created_at=older_time,
    )

    newer_low_id = TimeTransaction(
        id=UUID(
            "00000000-0000-0000-0000-000000000002"
        ),
        wallet_id=wallet.id,
        transaction_type="SESSION_RESERVE",
        available_seconds_delta=-1800,
        reserved_seconds_delta=1800,
        actor_user_id=admin.id,
        created_at=newer_time,
    )

    newer_high_id = TimeTransaction(
        id=UUID(
            "00000000-0000-0000-0000-000000000003"
        ),
        wallet_id=wallet.id,
        transaction_type="SESSION_USAGE",
        available_seconds_delta=0,
        reserved_seconds_delta=-1200,
        actor_user_id=admin.id,
        created_at=newer_time,
    )

    db_session.add_all(
        [
            older,
            newer_low_id,
            newer_high_id,
        ]
    )

    db_session.commit()

    response = client.get(
        (
            f"/admin/customers/"
            f"{customer.id}/time-transactions"
        ),
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    ids = [
        item["id"]
        for item in response.json()
    ]

    assert ids == [
        str(newer_high_id.id),
        str(newer_low_id.id),
        str(older.id),
    ]


def test_admin_time_history_supports_pagination(
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

    base_time = datetime(
        2026,
        8,
        16,
        12,
        0,
        tzinfo=timezone.utc,
    )

    transactions = [
        TimeTransaction(
            id=UUID(
                (
                    "00000000-0000-0000-0000-"
                    f"{index:012d}"
                )
            ),
            wallet_id=wallet.id,
            transaction_type="PURCHASE",
            available_seconds_delta=60,
            reserved_seconds_delta=0,
            actor_user_id=admin.id,
            created_at=base_time,
        )
        for index in range(1, 5)
    ]

    db_session.add_all(transactions)
    db_session.commit()

    response = client.get(
        (
            f"/admin/customers/"
            f"{customer.id}/time-transactions"
        ),
        params={
            "limit": 2,
            "offset": 1,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    ids = [
        item["id"]
        for item in response.json()
    ]

    assert ids == [
        str(transactions[2].id),
        str(transactions[1].id),
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
def test_admin_time_history_rejects_invalid_pagination(
    client,
    user_factory,
    auth_headers,
    params,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    customer = user_factory(
        username="cliente01",
    )

    response = client.get(
        (
            f"/admin/customers/"
            f"{customer.id}/time-transactions"
        ),
        params=params,
        headers=auth_headers(admin),
    )

    assert response.status_code == 422


def test_admin_wallet_and_history_reads_are_read_only(
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
        reserved_seconds=1800,
    )

    wallet = _get_wallet(
        db_session,
        customer.id,
    )

    transaction = TimeTransaction(
        wallet_id=wallet.id,
        transaction_type="SESSION_RESERVE",
        available_seconds_delta=-1800,
        reserved_seconds_delta=1800,
        actor_user_id=admin.id,
    )

    db_session.add(transaction)
    db_session.commit()
    db_session.refresh(transaction)

    wallet_before = (
        wallet.available_seconds,
        wallet.reserved_seconds,
        wallet.updated_at,
    )

    customer_before = (
        customer.username,
        customer.display_name,
        customer.is_active,
        customer.updated_at,
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

    wallet_response = client.get(
        (
            f"/admin/customers/"
            f"{customer.id}/wallet"
        ),
        headers=auth_headers(admin),
    )

    history_response = client.get(
        (
            f"/admin/customers/"
            f"{customer.id}/time-transactions"
        ),
        headers=auth_headers(admin),
    )

    assert wallet_response.status_code == 200
    assert history_response.status_code == 200

    db_session.expire_all()

    stored_customer = db_session.get(
        User,
        customer.id,
    )

    stored_wallet = db_session.get(
        TimeWallet,
        wallet.id,
    )

    assert stored_customer is not None
    assert stored_wallet is not None

    wallet_after = (
        stored_wallet.available_seconds,
        stored_wallet.reserved_seconds,
        stored_wallet.updated_at,
    )

    customer_after = (
        stored_customer.username,
        stored_customer.display_name,
        stored_customer.is_active,
        stored_customer.updated_at,
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

    assert wallet_after == wallet_before
    assert customer_after == customer_before

    assert (
        transaction_ids_after
        == transaction_ids_before
    )

    assert (
        transaction_count_after
        == transaction_count_before
    )