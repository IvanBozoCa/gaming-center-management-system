from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db,
    require_admin,
)
from app.models.user import User
from app.schemas.usage_session import (
    SessionFinishResponse,
    SessionStartCreate,
    SessionStartResponse,
)
from app.services.usage_session_service import (
    CustomerActiveSessionError,
    InsufficientTimeBalanceError,
    InvalidAuthorizedTimeError,
    SessionCustomerNotFoundError,
    SessionFinishConflictError,
    SessionInactiveCustomerError,
    SessionReservationMismatchError,
    SessionStartConflictError,
    SessionStationNotFoundError,
    SessionStationUnavailableError,
    SessionWalletNotFoundError,
    StationActiveSessionError,
    UsageSessionAlreadyFinishedError,
    UsageSessionNotFoundError,
    finish_registered_customer_session,
    start_registered_customer_session,
)


router = APIRouter(
    prefix="/admin/sessions",
    tags=["Admin - Sessions"],
)


@router.post(
    "",
    response_model=SessionStartResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_session(
    data: SessionStartCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        return start_registered_customer_session(
            db,
            station_id=data.station_id,
            customer_id=data.customer_id,
            authorized_seconds=(
                data.authorized_seconds
            ),
            actor_user_id=admin.id,
        )

    except InvalidAuthorizedTimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Authorized time must be "
                "greater than zero"
            ),
        ) from exc

    except SessionStationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found",
        ) from exc

    except SessionStationUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Station is not available",
        ) from exc

    except SessionCustomerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        ) from exc

    except SessionInactiveCustomerError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer is inactive",
        ) from exc

    except SessionWalletNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer wallet not found",
        ) from exc

    except InsufficientTimeBalanceError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Insufficient time balance",
        ) from exc

    except StationActiveSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Station already has "
                "an active session"
            ),
        ) from exc

    except CustomerActiveSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Customer already has "
                "an active session"
            ),
        ) from exc

    except SessionStartConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session start conflict",
        ) from exc
        
@router.post(
    "/{session_id}/finish",
    response_model=SessionFinishResponse,
    status_code=status.HTTP_200_OK,
)
def finish_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        return finish_registered_customer_session(
            db,
            session_id=session_id,
            actor_user_id=admin.id,
        )

    except UsageSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usage session not found",
        ) from exc

    except UsageSessionAlreadyFinishedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Usage session is already finished",
        ) from exc

    except SessionStationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session station not found",
        ) from exc

    except SessionWalletNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer wallet not found",
        ) from exc

    except SessionReservationMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Session reservation is "
                "inconsistent"
            ),
        ) from exc

    except SessionFinishConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session finish conflict",
        ) from exc