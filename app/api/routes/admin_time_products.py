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
from app.schemas.time_product import (
    TimeProductCreate,
    TimeProductResponse,
    TimeProductUpdate,
)
from app.services.time_product_service import (
    InvalidTimeProductNameError,
    TimeProductAlreadyExistsError,
    TimeProductNotFoundError,
    create_time_product,
    get_time_product,
    list_time_products,
    update_time_product,
)


router = APIRouter(
    prefix="/admin/time-products",
    tags=["Admin - Time Products"],
)


@router.post(
    "",
    response_model=TimeProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_time_product(
    data: TimeProductCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        return create_time_product(
            db,
            name=data.name,
            duration_seconds=data.duration_seconds,
            price_clp=data.price_clp,
        )

    except InvalidTimeProductNameError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail="Time product name is invalid",
        ) from exc

    except TimeProductAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Time product name already exists",
        ) from exc


@router.get(
    "",
    response_model=list[TimeProductResponse],
)
def get_time_products(
    is_active: bool | None = Query(
        default=None,
    ),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    return list_time_products(
        db,
        is_active=is_active,
    )


@router.get(
    "/{time_product_id}",
    response_model=TimeProductResponse,
)
def get_time_product_detail(
    time_product_id: UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        return get_time_product(
            db,
            time_product_id=time_product_id,
        )

    except TimeProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Time product not found",
        ) from exc


@router.patch(
    "/{time_product_id}",
    response_model=TimeProductResponse,
)
def change_time_product(
    time_product_id: UUID,
    data: TimeProductUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        return update_time_product(
            db,
            time_product_id=time_product_id,
            changes=data.model_dump(
                exclude_unset=True,
            ),
        )

    except TimeProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Time product not found",
        ) from exc

    except InvalidTimeProductNameError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ),
            detail="Time product name is invalid",
        ) from exc

    except TimeProductAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Time product name already exists",
        ) from exc