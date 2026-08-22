from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from app.services.station_session_events import (
    publish_active_session_event,
    publish_session_finish_event,
)
from sqlalchemy.orm import Session
from uuid import UUID
from app.api.deps import (
    get_db,
    require_admin,
)
from app.models.user import User
from app.schemas.usage_session import (
    GuestSessionStartCreate,
    GuestSessionStartResponse,
    ActiveGuestSessionResponse,
    GuestSessionFinishResponse,
    FinishedGuestSessionHistoryResponse,
)
from app.services.usage_session_service import (
    GuestSessionStartConflictError,
    InvalidAuthorizedTimeError,
    SessionStationNotFoundError,
    SessionStationUnavailableError,
    StationActiveSessionError,
    start_guest_session,
    list_active_guest_sessions,
    GuestSessionFinishConflictError,
    GuestSessionNotFoundError,
    UsageSessionAlreadyFinishedError,
    finish_guest_session,
    list_finished_guest_sessions,
)


router = APIRouter(
    prefix="/admin/guest-sessions",
    tags=["Admin - Guest Sessions"],
)


@router.post(
    "",
    response_model=GuestSessionStartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar sesión prepago de invitado",
    description=(
        "Inicia una sesión temporal para un invitado "
        "sin crear usuario, billetera ni movimientos "
        "de saldo. El tiempo autorizado corresponde "
        "únicamente a esta sesión."
    ),
)
def create_guest_session(
    data: GuestSessionStartCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        result = start_guest_session(
            db,
            station_id=data.station_id,
            authorized_seconds=(
                data.authorized_seconds
            ),
)

        publish_active_session_event(
            db,
            station_id=result.station_id,
            session_id=result.session_id,
            event_type="SESSION_START",
        )

        return result

    except InvalidAuthorizedTimeError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
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

    except StationActiveSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Station already has "
                "an active session"
            ),
        ) from exc

    except GuestSessionStartConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Guest session start conflict",
        ) from exc


@router.post(
    "/{session_id}/finish",
    response_model=GuestSessionFinishResponse,
    status_code=status.HTTP_200_OK,
    summary="Finalizar sesión de invitado",
    description=(
        "Finaliza una sesión GUEST activa usando "
        "el reloj del servidor. El tiempo no "
        "utilizado se informa como unused_seconds "
        "y no se acredita a ninguna billetera."
    ),
)
def finish_guest_usage_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        result = finish_guest_session(
            db,
            session_id=session_id,
        )

        publish_session_finish_event(
            station_id=result.station_id,
            session_id=result.session_id,
            session_type="GUEST",
            ended_at=result.ended_at,
        )

        return result

    except GuestSessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest session not found",
        ) from exc

    except UsageSessionAlreadyFinishedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Guest session is already finished"
            ),
        ) from exc

    except SessionStationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Guest session station not found",
        ) from exc

    except GuestSessionFinishConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Guest session finish conflict",
        ) from exc
        


@router.get(
    "/active",
    response_model=list[
        ActiveGuestSessionResponse
    ],
    status_code=status.HTTP_200_OK,
    summary="Consultar sesiones guest activas",
    description=(
        "Devuelve las sesiones de invitados "
        "actualmente activas. El tiempo transcurrido "
        "y restante se calcula usando el reloj del "
        "servidor y la consulta no modifica datos."
    ),
)
def get_active_guest_sessions(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return list_active_guest_sessions(
        db,
    )

@router.get(
    "/history",
    response_model=list[
        FinishedGuestSessionHistoryResponse
    ],
    status_code=status.HTTP_200_OK,
    summary="Consultar historial de sesiones guest",
    description=(
        "Devuelve únicamente sesiones GUEST "
        "finalizadas, ordenadas desde el cierre "
        "más reciente al más antiguo por ended_at "
        "DESC e id DESC. Permite filtrar "
        "opcionalmente por estación. La operación "
        "es exclusivamente de lectura."
    ),
)
def get_guest_session_history(
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
    return list_finished_guest_sessions(
        db,
        station_id=station_id,
        limit=limit,
        offset=offset,
    )