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
from app.schemas.station import (
    StationCreate,
    StationResponse,
)
from app.services.station_service import (
    InvalidStationCodeError,
    StationAlreadyExistsError,
    create_station,
    list_stations,
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