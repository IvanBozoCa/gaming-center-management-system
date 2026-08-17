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
    GuestSessionStartCreate,
    GuestSessionStartResponse,
    ActiveGuestSessionResponse,
)
from app.services.usage_session_service import (
    GuestSessionStartConflictError,
    InvalidAuthorizedTimeError,
    SessionStationNotFoundError,
    SessionStationUnavailableError,
    StationActiveSessionError,
    start_guest_session,
    list_active_guest_sessions,
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
        return start_guest_session(
            db,
            station_id=data.station_id,
            authorized_seconds=(
                data.authorized_seconds
            ),
        )

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