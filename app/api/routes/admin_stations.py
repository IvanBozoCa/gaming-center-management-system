from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session
from uuid import UUID
from app.api.deps import (
    get_db,
    require_admin,
)
from app.models.user import User
from app.schemas.station import (
    StationCreate,
    StationResponse,
    StationStatusUpdate,
)
from app.services.station_service import (
    InvalidStationCodeError,
    InvalidStationStatusError,
    StationAlreadyExistsError,
    StationInUseError,
    StationNotFoundError,
    create_station,
    list_stations,
    update_station_status,
)

router = APIRouter(
    prefix="/admin/stations",
    tags=["Admin - Stations"],
)


@router.post(
    "",
    response_model=StationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_station(
    data: StationCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        return create_station(
            db,
            code=data.code,
        )

    except InvalidStationCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Station code is invalid",
        ) from exc

    except StationAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Station code already exists",
        ) from exc


@router.get(
    "",
    response_model=list[StationResponse],
)
def get_stations(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return list_stations(db)

@router.patch(
    "/{station_id}/status",
    response_model=StationResponse,
    status_code=status.HTTP_200_OK,
    summary="Cambiar estado operativo de una estación",
    description=(
        "Permite al administrador establecer una "
        "estación como AVAILABLE, MAINTENANCE u "
        "OFFLINE. El estado IN_USE es administrado "
        "exclusivamente por el ciclo de vida de las "
        "sesiones. Una estación en uso o con una "
        "sesión activa no puede modificarse mediante "
        "esta operación."
    ),
)
def change_station_status(
    station_id: UUID,
    data: StationStatusUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        return update_station_status(
            db,
            station_id=station_id,
            status=data.status,
        )

    except StationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found",
        ) from exc

    except StationInUseError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Station is currently in use",
        ) from exc

    except InvalidStationStatusError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail=(
                "Station status cannot be "
                "assigned manually"
            ),
        ) from exc
        
        