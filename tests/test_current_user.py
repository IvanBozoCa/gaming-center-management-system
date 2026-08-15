from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User


def register_and_login(client):
    register_response = client.post(
        "/auth/register",
        json={
            "username": "cliente01",
            "display_name": "Cliente Prueba",
            "password": "Prueba123!",
        },
    )

    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        data={
            "username": "cliente01",
            "password": "Prueba123!",
        },
    )

    assert login_response.status_code == 200

    return login_response.json()["access_token"]

def test_get_current_user_with_valid_token(
    client,
    db_session: Session,
):
    token = register_and_login(client)

    user = db_session.scalar(
        select(User).where(
            User.username == "cliente01"
        )
    )

    assert user is not None

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == str(user.id)
    assert data["username"] == "cliente01"
    assert data["display_name"] == "Cliente Prueba"
    assert data["role"] == "CUSTOMER"
    assert data["is_active"] is True

    assert "password" not in data
    assert "password_hash" not in data
def test_get_current_user_without_token_returns_401(
    client,
):
    response = client.get(
        "/auth/me"
    )

    assert response.status_code == 401
    
def test_get_current_user_with_invalid_token_returns_401(
    client,
):
    response = client.get(
        "/auth/me",
        headers={
            "Authorization": "Bearer esto-no-es-un-jwt"
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Could not validate credentials"
    }

    assert (
        response.headers["www-authenticate"]
        == "Bearer"
    )
def test_get_current_user_with_expired_token_returns_401(
    client,
    db_session: Session,
):
    register_and_login(client)

    user = db_session.scalar(
        select(User).where(
            User.username == "cliente01"
        )
    )

    assert user is not None

    now = datetime.now(timezone.utc)

    expired_token = jwt.encode(
        {
            "sub": str(user.id),
            "iat": now - timedelta(minutes=10),
            "exp": now - timedelta(minutes=5),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {expired_token}"
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Could not validate credentials"
    }
def test_token_for_nonexistent_user_returns_401(
    client,
):
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "iat": datetime.now(timezone.utc),
            "exp": (
                datetime.now(timezone.utc)
                + timedelta(minutes=30)
            ),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Could not validate credentials"
    }
def test_inactive_user_with_existing_token_returns_401(
    client,
    db_session: Session,
):
    token = register_and_login(client)

    user = db_session.scalar(
        select(User).where(
            User.username == "cliente01"
        )
    )

    assert user is not None

    user.is_active = False
    db_session.commit()

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Could not validate credentials"
    }
    
def test_token_with_invalid_subject_returns_401(
    client,
):
    now = datetime.now(timezone.utc)

    token = jwt.encode(
        {
            "sub": "esto-no-es-un-uuid",
            "iat": now,
            "exp": now + timedelta(minutes=30),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Could not validate credentials"
    }