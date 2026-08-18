from collections.abc import Generator
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.user import User
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
    OAuth2PasswordBearer,
)
from app.models.station import Station

from app.services.station_service import (
    authenticate_station_agent,
)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/login"
)
station_agent_scheme = HTTPBearer(
    scheme_name="StationAgentBearer",
    auto_error=False,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )

    try:
        payload = decode_access_token(token)

        user_id = UUID(
            payload["sub"]
        )

    except (
        InvalidTokenError,
        KeyError,
        ValueError,
        TypeError,
    ) as exc:
        raise credentials_exception from exc

    user = db.scalar(
        select(User).where(
            User.id == user_id
        )
    )

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise credentials_exception

    return user

def require_admin(
    current_user: User = Depends(
        get_current_user
    ),
) -> User:
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )

    return current_user

def get_current_station_agent(
    credentials: (
        HTTPAuthorizationCredentials
        | None
    ) = Depends(
        station_agent_scheme
    ),
    db: Session = Depends(get_db),
) -> Station:
    credentials_exception = (
        HTTPException(
            status_code=(
                status.HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "Could not validate "
                "station agent credentials"
            ),
            headers={
                "WWW-Authenticate":
                    "Bearer",
            },
        )
    )

    if (
        credentials is None
        or credentials.scheme.lower()
        != "bearer"
    ):
        raise credentials_exception

    station = (
        authenticate_station_agent(
            db,
            token=(
                credentials.credentials
            ),
        )
    )

    if station is None:
        raise credentials_exception

    return station