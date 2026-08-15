from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_db,
    require_admin,
)
from app.core.security import create_access_token
from app.schemas.auth import TokenResponse
from app.schemas.user import (
    CurrentUserResponse,
    UserRegister,
    UserResponse,
)
from app.models.user import User
from app.services.auth_service import (
    InvalidCredentialsError,
    authenticate_user,
)
from app.services.user_service import (
    RegistrationConflictError,
    UsernameAlreadyExistsError,
    create_customer,
)
router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_customer(
    data: UserRegister,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        return create_customer(db, data)

    except UsernameAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered",
        ) from exc

    except RegistrationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to create user due to conflicting data",
        ) from exc
        
@router.post(
    "/login",
    response_model=TokenResponse,
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    try:
        user = authenticate_user(
            db,
            form_data.username,
            form_data.password,
        )

    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from exc

    access_token = create_access_token(
        subject=str(user.id)
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
    )
    
@router.get(
    "/me",
    response_model=CurrentUserResponse,
)
def get_authenticated_user(
    current_user: User = Depends(
        get_current_user
    ),
):
    return current_user