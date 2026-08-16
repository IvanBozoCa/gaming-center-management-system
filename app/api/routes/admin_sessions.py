from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db,
    require_admin,
)
from app.models.user import User
from app.schemas.usage_session import (
    ActiveSessionResponse,
    SessionExtensionCreate,
    SessionExtensionResponse,
    SessionFinishResponse,
    SessionStartCreate,
    SessionStartResponse,
    FinishedSessionHistoryResponse,
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
    list_active_registered_customer_sessions,
    InvalidAdditionalTimeError,
    SessionExtensionConflictError,
    extend_registered_customer_session,
    list_finished_registered_customer_sessions,
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
        

@router.get(
    "/active",
    response_model=list[ActiveSessionResponse],
    status_code=status.HTTP_200_OK,
)
def list_active_sessions(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return list_active_registered_customer_sessions(
        db,
    )


@router.get(
    "/history",
    response_model=list[
        FinishedSessionHistoryResponse
    ],
    status_code=status.HTTP_200_OK,
    summary="Consultar historial de sesiones finalizadas",
    description=(
        "Devuelve únicamente sesiones FINISHED, "
        "ordenadas desde el cierre más reciente al "
        "más antiguo por ended_at DESC e id DESC. "
        "Permite filtrar opcionalmente por cliente "
        "y estación. La operación es exclusivamente "
        "de lectura."
    ),
)
def list_finished_sessions(
    customer_id: UUID | None = Query(
        default=None,
    ),
    station_id: UUID | None = Query(
        default=None,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return (
        list_finished_registered_customer_sessions(
            db,
            customer_id=customer_id,
            station_id=station_id,
            limit=limit,
            offset=offset,
        )
    )


@router.post(
    "/{session_id}/extend",
    response_model=SessionExtensionResponse,
    status_code=status.HTTP_200_OK,
)
def extend_session(
    session_id: UUID,
    data: SessionExtensionCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        return extend_registered_customer_session(
            db,
            session_id=session_id,
            additional_seconds=(
                data.additional_seconds
            ),
            actor_user_id=admin.id,
        )

    except InvalidAdditionalTimeError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Additional time must be "
                "greater than zero"
            ),
        ) from exc

    except UsageSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usage session not found",
        ) from exc

    except UsageSessionAlreadyFinishedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Usage session is already finished"
            ),
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

    except SessionExtensionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session extension conflict",
        ) from exc