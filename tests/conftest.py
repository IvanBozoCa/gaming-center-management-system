import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models
from app.core.security import (
    create_access_token,
    hash_password,
)
from app.models.time_wallet import TimeWallet
from app.models.user import User
from app.api.deps import get_db
from app.core.config import settings
from app.core.database import Base
from app.main import app

if settings.test_db_name == settings.db_name:
    raise RuntimeError(
        "TEST_DB_NAME must be different from DB_NAME"
    )


TEST_DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=settings.db_user,
    password=settings.db_password,
    host=settings.db_host,
    port=settings.db_port,
    database=settings.test_db_name,
)

test_engine = create_engine(
    TEST_DATABASE_URL,
    pool_pre_ping=True,
)


TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture()
def db_session():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def client(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    
@pytest.fixture()
def user_factory(
    db_session: Session,
):
    def create_user(
        username: str = "cliente01",
        display_name: str = "Cliente Prueba",
        password: str = "Prueba123!",
        role: str = "CUSTOMER",
        is_active: bool = True,
        available_seconds: int = 0,
        reserved_seconds: int = 0,
    ) -> User:
        user = User(
            username=username,
            display_name=display_name,
            password_hash=hash_password(password),
            role=role,
            is_active=is_active,
        )

        db_session.add(user)

        if role == "CUSTOMER":
            wallet = TimeWallet(
                user=user,
                available_seconds=available_seconds,
                reserved_seconds=reserved_seconds,
            )

            db_session.add(wallet)

        db_session.commit()
        db_session.refresh(user)

        return user

    return create_user


@pytest.fixture()
def auth_headers():
    def build_headers(
        user: User,
    ) -> dict[str, str]:
        token = create_access_token(
            subject=str(user.id)
        )

        return {
            "Authorization": f"Bearer {token}"
        }

    return build_headers