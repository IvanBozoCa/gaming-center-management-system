from datetime import datetime, timezone

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User

def test_login_success_returns_valid_token(
    client,
    db_session: Session,
    user_factory,
):
    user = user_factory(
        username="cliente01",
        display_name="Cliente Prueba",
        password="Prueba123!",
    )

    login_response = client.post(
        "/auth/login",
        data={
            "username": "cliente01",
            "password": "Prueba123!",
        },
    )

    assert login_response.status_code == 200

    data = login_response.json()

    assert "access_token" in data
    assert data["token_type"] == "bearer"

    payload = jwt.decode(
        data["access_token"],
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )

    assert payload["sub"] == str(user.id)
    assert "password" not in data
    assert "password_hash" not in data

    assert "iat" in payload
    assert "exp" in payload

    now_timestamp = int(
        datetime.now(timezone.utc).timestamp()
    )

    assert payload["exp"] > now_timestamp
       
def test_login_wrong_password_returns_401(
    client,
    user_factory,
):
    user_factory(
        username="cliente01",
        password="Prueba123!",
    )

    response = client.post(
        "/auth/login",
        data={
            "username": "cliente01",
            "password": "incorrecta",
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Incorrect username or password"
    }

    assert response.headers["www-authenticate"] == "Bearer"
    
    
def test_login_nonexistent_user_returns_same_error(
    client,
):
    response = client.post(
        "/auth/login",
        data={
            "username": "usuario_inexistente",
            "password": "Prueba123!",
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Incorrect username or password"
    }

    assert response.headers["www-authenticate"] == "Bearer"
    
def test_invalid_credentials_use_same_public_response(
    client,
    user_factory,
):
    user_factory(
        username="cliente01",
        password="Prueba123!",
    )

    wrong_password_response = client.post(
        "/auth/login",
        data={
            "username": "cliente01",
            "password": "incorrecta",
        },
    )

    nonexistent_user_response = client.post(
        "/auth/login",
        data={
            "username": "no_existe",
            "password": "Prueba123!",
        },
    )

    assert wrong_password_response.status_code == 401
    assert nonexistent_user_response.status_code == 401

    assert (
        wrong_password_response.json()
        == nonexistent_user_response.json()
    )
    
def test_inactive_user_cannot_login(
    client,
    db_session: Session,
    user_factory,
):
    user_factory(
        username="cliente01",
        password="Prueba123!",
        is_active=False,
    )

    user = db_session.scalar(
        select(User).where( 
            User.username == "cliente01"
        )
    )

    assert user is not None

    user.is_active = False

    db_session.commit()

    response = client.post(
        "/auth/login",
        data={
            "username": "cliente01",
            "password": "Prueba123!",
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Incorrect username or password"
    }

    assert "access_token" not in response.json()
    
def test_login_normalizes_username(
    client,
    user_factory,
):
    user_factory(
        username="cliente01",
        password="Prueba123!",
    )

    response = client.post(
        "/auth/login",
        data={
            "username": "  CLIENTE01  ",
            "password": "Prueba123!",
        },
    )

    assert response.status_code == 200
    assert "access_token" in response.json()