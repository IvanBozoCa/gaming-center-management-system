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
from app.schemas.time_sale import (
    GuestTimeSaleCreate,
    RegisteredTimeSaleCreate,
    TimeSaleCreate,
    TimeSaleResponse,
)
from app.services.time_product_service import (
    TimeProductNotFoundError,
)
from app.services.time_sale_service import (
    InactiveTimeProductError,
    create_guest_time_sale,
    create_registered_time_sale,
)
from app.services.time_wallet_service import (
    CustomerNotFoundError,
    CustomerWalletNotFoundError,
    InactiveCustomerError,
)
from app.services.usage_session_service import (
    GuestSessionStartConflictError,
    SessionStationNotFoundError,
    SessionStationUnavailableError,
    StationActiveSessionError,
)


router = APIRouter(
    prefix="/admin/time-sales",
    tags=["Admin - Time Sales"],
)


@router.post(
    "",
    response_model=TimeSaleResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_time_sale(
    data: TimeSaleCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        if isinstance(
            data,
            RegisteredTimeSaleCreate,
        ):
            return create_registered_time_sale(
                db,
                time_product_id=(
                    data.time_product_id
                ),
                customer_id=data.customer_id,
                actor_user_id=admin.id,
            )

        if isinstance(
            data,
            GuestTimeSaleCreate,
        ):
            return create_guest_time_sale(
                db,
                time_product_id=(
                    data.time_product_id
                ),
                station_id=data.station_id,
                actor_user_id=admin.id,
            )

        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail="Invalid sale type",
        )

    except TimeProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Time product not found",
        ) from exc

    except InactiveTimeProductError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Time product is inactive",
        ) from exc

    except CustomerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        ) from exc

    except InactiveCustomerError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer is inactive",
        ) from exc

    except CustomerWalletNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer wallet not found",
        ) from exc

    except SessionStationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Station not found",
        ) from exc

    except (
        SessionStationUnavailableError,
        StationActiveSessionError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Station is unavailable",
        ) from exc

    except GuestSessionStartConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Guest session start conflict",
        ) from exc