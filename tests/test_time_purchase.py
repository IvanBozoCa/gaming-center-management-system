import pytest
from sqlalchemy import select
from uuid import uuid4
from app.models.time_transaction import TimeTransaction
from app.models.time_wallet import TimeWallet
from app.services.time_wallet_service import (
    InvalidTimeAmountError,
    register_time_purchase,
)

def test_admin_can_credit_time_and_create_purchase_transaction(
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

    response = client.post(
        (
            f"/admin/customers/"
            f"{customer.id}/time-purchases"
        ),
        json={
            "seconds": 3600,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["customer_id"] == str(customer.id)
    assert data["credited_seconds"] == 3600
    assert data["available_seconds"] == 5400
    assert data["reserved_seconds"] == 0
    assert data["transaction_type"] == "PURCHASE"
    assert data["transaction_id"]
    assert data["created_at"]

    wallet = db_session.scalar(
        select(TimeWallet).where(
            TimeWallet.user_id == customer.id
        )
    )

    assert wallet is not None
    assert wallet.available_seconds == 5400
    assert wallet.reserved_seconds == 0

    transactions = db_session.scalars(
        select(TimeTransaction).where(
            TimeTransaction.wallet_id == wallet.id
        )
    ).all()

    assert len(transactions) == 1

    transaction = transactions[0]

    assert transaction.transaction_type == "PURCHASE"
    assert transaction.available_seconds_delta == 3600
    assert transaction.reserved_seconds_delta == 0
    assert transaction.actor_user_id == admin.id
    

def test_multiple_time_purchases_accumulate_balance_and_history(
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

    url = (
        f"/admin/customers/"
        f"{customer.id}/time-purchases"
    )

    first_response = client.post(
        url,
        json={"seconds": 3600},
        headers=auth_headers(admin),
    )

    second_response = client.post(
        url,
        json={"seconds": 1800},
        headers=auth_headers(admin),
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    assert first_response.json()["available_seconds"] == 3600
    assert second_response.json()["available_seconds"] == 5400

    wallet = db_session.scalar(
        select(TimeWallet).where(
            TimeWallet.user_id == customer.id
        )
    )

    assert wallet.available_seconds == 5400

    transactions = db_session.scalars(
        select(TimeTransaction).where(
            TimeTransaction.wallet_id == wallet.id
        )
    ).all()

    assert len(transactions) == 2

    assert sum(
        transaction.available_seconds_delta
        for transaction in transactions
    ) == 5400
    

def test_customer_cannot_credit_time(
    client,
    user_factory,
    auth_headers,
):
    acting_customer = user_factory(
        username="cliente01",
    )

    target_customer = user_factory(
        username="cliente02",
    )

    response = client.post(
        (
            f"/admin/customers/"
            f"{target_customer.id}/time-purchases"
        ),
        json={
            "seconds": 3600,
        },
        headers=auth_headers(acting_customer),
    )

    assert response.status_code == 403

    assert response.json() == {
        "detail": "Admin privileges required"
    }


def test_time_purchase_without_token_returns_401(
    client,
    user_factory,
):
    customer = user_factory(
        username="cliente01",
    )

    response = client.post(
        (
            f"/admin/customers/"
            f"{customer.id}/time-purchases"
        ),
        json={
            "seconds": 3600,
        },
    )

    assert response.status_code == 401
    
    
def test_time_purchase_for_unknown_customer_returns_404(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    unknown_customer_id = uuid4()

    response = client.post(
        (
            f"/admin/customers/"
            f"{unknown_customer_id}/time-purchases"
        ),
        json={
            "seconds": 3600,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Customer not found"
    }
    

def test_cannot_credit_time_to_inactive_customer(
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
        is_active=False,
    )

    response = client.post(
        (
            f"/admin/customers/"
            f"{customer.id}/time-purchases"
        ),
        json={
            "seconds": 3600,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 409

    assert response.json() == {
        "detail": "Customer is inactive"
    }

    wallet = db_session.scalar(
        select(TimeWallet).where(
            TimeWallet.user_id == customer.id
        )
    )

    assert wallet.available_seconds == 1800

    transactions = db_session.scalars(
        select(TimeTransaction).where(
            TimeTransaction.wallet_id == wallet.id
        )
    ).all()

    assert transactions == []
    

@pytest.mark.parametrize(
    "seconds",
    [
        0,
        -1,
        -3600,
    ],
)
def test_time_purchase_requires_positive_seconds(
    client,
    user_factory,
    auth_headers,
    seconds,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    customer = user_factory(
        username="cliente01",
    )

    response = client.post(
        (
            f"/admin/customers/"
            f"{customer.id}/time-purchases"
        ),
        json={
            "seconds": seconds,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 422


def test_time_purchase_service_rejects_non_positive_seconds(
    db_session,
    user_factory,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    customer = user_factory(
        username="cliente01",
        available_seconds=1800,
    )

    with pytest.raises(InvalidTimeAmountError):
        register_time_purchase(
            db_session,
            customer_id=customer.id,
            seconds=0,
            actor_user_id=admin.id,
        )

    wallet = db_session.scalar(
        select(TimeWallet).where(
            TimeWallet.user_id == customer.id
        )
    )

    assert wallet.available_seconds == 1800   


def test_time_purchase_response_is_safe_for_admin_ui(
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
        (
            f"/admin/customers/"
            f"{customer.id}/time-purchases"
        ),
        json={
            "seconds": 3600,
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 201

    data = response.json()

    assert set(data.keys()) == {
        "transaction_id",
        "customer_id",
        "credited_seconds",
        "available_seconds",
        "reserved_seconds",
        "transaction_type",
        "created_at",
    }

    assert "password" not in data
    assert "password_hash" not in data
    assert "actor_user_id" not in data