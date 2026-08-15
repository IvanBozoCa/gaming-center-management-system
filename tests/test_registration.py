from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.time_wallet import TimeWallet
from app.models.user import User

def test_register_customer_success(
    client,
    db_session: Session,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin",
        display_name="Administrador",
        role="ADMIN",
    )

    payload = {
        "username": "cliente01",
        "display_name": "Cliente Prueba",
        "password": "Prueba123!",
    }

    response = client.post(
        "/auth/register",
        json=payload,
        headers=auth_headers(admin),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["username"] == "cliente01"
    assert data["display_name"] == "Cliente Prueba"
    assert data["role"] == "CUSTOMER"
    assert data["is_active"] is True

    assert "password" not in data
    assert "password_hash" not in data

    user = db_session.scalar(
        select(User).where(
            User.username == "cliente01"
        )
    )

    assert user is not None
    assert user.role == "CUSTOMER"

    assert user.password_hash != payload["password"]

    assert verify_password(
        payload["password"],
        user.password_hash,
    )

    wallet = db_session.scalar(
        select(TimeWallet).where(
            TimeWallet.user_id == user.id
        )
    )

    assert wallet is not None
    assert wallet.available_seconds == 0
    assert wallet.reserved_seconds == 0    
    
def test_register_duplicate_username_returns_409(
    client,
    db_session: Session,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin",
        display_name="Administrador",
        role="ADMIN",
    )
    
    payload = {
        "username": "cliente01",
        "display_name": "Cliente Prueba",
        "password": "Prueba123!",
    }

    first_response = client.post(
        "/auth/register",
        json=payload,
        headers=auth_headers(admin),
    )

    second_response = client.post(
        "/auth/register",
        json=payload,
        headers=auth_headers(admin),
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409

    assert second_response.json() == {
        "detail": "Username already registered"
    }

    customer_count = db_session.scalar(
        select(func.count())
        .select_from(User)
        .where(
            User.role == "CUSTOMER"
        ))   
    assert customer_count == 1
    
def test_register_invalid_data_does_not_persist(
    
    client,
    db_session: Session,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin",
        display_name="Administrador",
        role="ADMIN",
    )
    payload = {
        "username": "ab",
        "display_name": "X",
        "password": "123",
    }

    response = client.post(
        "/auth/register",
        json=payload,
        headers=auth_headers(admin),
    )

    assert response.status_code == 422

    customer_count = db_session.scalar(
        select(func.count())
        .select_from(User)
        .where(
            User.role == "CUSTOMER"
        )
)

    assert customer_count == 0
    
def test_register_cannot_set_role(
    client,
    db_session: Session,
    user_factory,
    auth_headers,
):
    admin = user_factory(
        username="admin",
        display_name="Administrador",
        role="ADMIN",
    )
    payload = {
        "username": "hacker",
        "display_name": "Prueba",
        "password": "Prueba123!",
        "role": "ADMIN",
    }

    response = client.post(
        "/auth/register",
        json=payload,
        headers=auth_headers(admin),
    )

    assert response.status_code == 422

    customer_count = db_session.scalar(
        select(func.count())
        .select_from(User)
        .where(
            User.role == "CUSTOMER"
        )
)
    assert customer_count == 0