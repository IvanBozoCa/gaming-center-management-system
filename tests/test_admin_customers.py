import pytest
from sqlalchemy import func, select

from app.models.time_transaction import (
    TimeTransaction,
)
from app.models.time_wallet import TimeWallet
from app.models.user import User


def test_admin_can_list_customers_with_wallet_balance(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        display_name="Administrador",
        role="ADMIN",
    )

    customer_one = user_factory(
        username="juan01",
        display_name="Juan Perez",
        available_seconds=7200,
        reserved_seconds=1800,
    )

    customer_two = user_factory(
        username="maria01",
        display_name="Maria Soto",
        available_seconds=3600,
        reserved_seconds=0,
    )

    response = client.get(
        "/admin/customers",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 2

    usernames = {
        item["username"]
        for item in data
    }

    assert usernames == {
        customer_one.username,
        customer_two.username,
    }

    assert "admin01" not in usernames

    customer_by_username = {
        item["username"]: item
        for item in data
    }

    juan = customer_by_username["juan01"]

    assert juan["id"] == str(customer_one.id)
    assert juan["display_name"] == "Juan Perez"
    assert juan["is_active"] is True
    assert juan["available_seconds"] == 7200
    assert juan["reserved_seconds"] == 1800

    assert set(juan) == {
        "id",
        "username",
        "display_name",
        "is_active",
        "created_at",
        "available_seconds",
        "reserved_seconds",
    }


def test_customer_cannot_list_admin_customers(
    client,
    user_factory,
    auth_headers,
):
    customer = user_factory(
        username="cliente01",
    )

    response = client.get(
        "/admin/customers",
        headers=auth_headers(customer),
    )

    assert response.status_code == 403


def test_admin_customer_list_requires_authentication(
    client,
):
    response = client.get(
        "/admin/customers",
    )

    assert response.status_code == 401


def test_admin_can_search_customers_case_insensitively(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    user_factory(
        username="juan01",
        display_name="Juan Perez",
    )

    user_factory(
        username="maria01",
        display_name="Maria Soto",
    )

    username_response = client.get(
        "/admin/customers",
        params={
            "q": "  JUAN01  ",
        },
        headers=auth_headers(admin),
    )

    assert username_response.status_code == 200

    username_data = username_response.json()

    assert len(username_data) == 1
    assert (
        username_data[0]["username"]
        == "juan01"
    )

    display_name_response = client.get(
        "/admin/customers",
        params={
            "q": "pErEz",
        },
        headers=auth_headers(admin),
    )

    assert (
        display_name_response.status_code
        == 200
    )

    display_name_data = (
        display_name_response.json()
    )

    assert len(display_name_data) == 1
    assert (
        display_name_data[0]["username"]
        == "juan01"
    )


def test_blank_customer_search_behaves_as_no_filter(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    user_factory(
        username="cliente01",
        display_name="Cliente Uno",
    )

    user_factory(
        username="cliente02",
        display_name="Cliente Dos",
    )

    response = client.get(
        "/admin/customers",
        params={
            "q": "   ",
        },
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    usernames = {
        item["username"]
        for item in response.json()
    }

    assert usernames == {
        "cliente01",
        "cliente02",
    }


def test_admin_can_filter_customers_by_active_status(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    user_factory(
        username="activo01",
        display_name="Cliente Activo",
        is_active=True,
    )

    user_factory(
        username="inactivo01",
        display_name="Cliente Inactivo",
        is_active=False,
    )

    active_response = client.get(
        "/admin/customers",
        params={
            "is_active": "true",
        },
        headers=auth_headers(admin),
    )

    assert active_response.status_code == 200

    assert [
        item["username"]
        for item in active_response.json()
    ] == [
        "activo01",
    ]

    inactive_response = client.get(
        "/admin/customers",
        params={
            "is_active": "false",
        },
        headers=auth_headers(admin),
    )

    assert (
        inactive_response.status_code
        == 200
    )

    assert [
        item["username"]
        for item in inactive_response.json()
    ] == [
        "inactivo01",
    ]


def test_admin_customer_list_has_deterministic_pagination(
    client,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin01",
        role="ADMIN",
    )

    user_factory(
        username="zeta01",
        display_name="Carlos",
    )

    user_factory(
        username="ana01",
        display_name="Ana",
    )

    user_factory(
        username="beta01",
        display_name="Carlos",
    )

    full_response = client.get(
        "/admin/customers",
        headers=auth_headers(admin),
    )

    assert full_response.status_code == 200

    assert [
        item["username"]
        for item in full_response.json()
    ] == [
        "ana01",
        "beta01",
        "zeta01",
    ]

    paginated_response = client.get(
        "/admin/customers",
        params={
            "limit": 2,
            "offset": 1,
        },
        headers=auth_headers(admin),
    )

    assert (
        paginated_response.status_code
        == 200
    )

    assert [
        item["username"]
        for item in paginated_response.json()
    ] == [
        "beta01",
        "zeta01",
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
def test_admin_customer_list_rejects_invalid_pagination(
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
        "/admin/customers",
        params=params,
        headers=auth_headers(admin),
    )

    assert response.status_code == 422


def test_admin_customer_list_is_read_only(
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

    wallet = db_session.scalar(
        select(TimeWallet).where(
            TimeWallet.user_id
            == customer.id
        )
    )

    assert wallet is not None

    customer_before = (
        customer.username,
        customer.display_name,
        customer.is_active,
        customer.updated_at,
    )

    wallet_before = (
        wallet.available_seconds,
        wallet.reserved_seconds,
    )

    users_before = db_session.scalar(
        select(func.count()).select_from(
            User
        )
    )

    wallets_before = db_session.scalar(
        select(func.count()).select_from(
            TimeWallet
        )
    )

    transactions_before = db_session.scalar(
        select(func.count()).select_from(
            TimeTransaction
        )
    )

    response = client.get(
        "/admin/customers",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200

    db_session.expire_all()

    stored_customer = db_session.get(
        User,
        customer.id,
    )

    stored_wallet = db_session.scalar(
        select(TimeWallet).where(
            TimeWallet.user_id
            == customer.id
        )
    )

    assert stored_customer is not None
    assert stored_wallet is not None

    customer_after = (
        stored_customer.username,
        stored_customer.display_name,
        stored_customer.is_active,
        stored_customer.updated_at,
    )

    wallet_after = (
        stored_wallet.available_seconds,
        stored_wallet.reserved_seconds,
    )

    users_after = db_session.scalar(
        select(func.count()).select_from(
            User
        )
    )

    wallets_after = db_session.scalar(
        select(func.count()).select_from(
            TimeWallet
        )
    )

    transactions_after = db_session.scalar(
        select(func.count()).select_from(
            TimeTransaction
        )
    )

    assert customer_after == customer_before
    assert wallet_after == wallet_before

    assert users_after == users_before
    assert wallets_after == wallets_before
    assert (
        transactions_after
        == transactions_before
    )