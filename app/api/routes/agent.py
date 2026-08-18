from fastapi import (
    APIRouter,
    Depends,
)
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_station_agent,
    get_db,
)
from app.models.station import Station
from app.schemas.station import (
    StationAgentResponse,
)
from app.services.station_service import (
    record_station_heartbeat,
)


router = APIRouter(
    prefix="/agent",
    tags=["Station Agent"],
)


@router.get(
    "/station",
    response_model=StationAgentResponse,
)
def get_agent_station(
    station: Station = Depends(
        get_current_station_agent
    ),
):
    return station


@router.post(
    "/heartbeat",
    response_model=StationAgentResponse,
)
def heartbeat(
    db: Session = Depends(get_db),
    station: Station = Depends(
        get_current_station_agent
    ),
):
    return record_station_heartbeat(
        db,
        station_id=station.id,
    )