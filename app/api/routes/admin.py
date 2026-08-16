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
from app.schemas.time_purchase import (
    TimePurchaseCreate,
    TimePurchaseResponse,
)
from app.services.time_wallet_service import (
    CustomerNotFoundError,
    CustomerWalletNotFoundError,
    InactiveCustomerError,
    InvalidTimeAmountError,
    register_time_purchase,
)


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


@router.post(
    "/customers/{customer_id}/time-purchases",
    response_model=TimePurchaseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_time_purchase(
    customer_id: UUID,
    data: TimePurchaseCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    try:
        return register_time_purchase(
            db,
            customer_id=customer_id,
            seconds=data.seconds,
            actor_user_id=admin.id,
        )

    except InvalidTimeAmountError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Time amount must be greater than zero",
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