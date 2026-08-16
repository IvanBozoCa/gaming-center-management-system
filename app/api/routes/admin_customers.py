from fastapi import (
    APIRouter,
    Depends,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db,
    require_admin,
)
from app.models.user import User
from app.schemas.admin_customer import (
    AdminCustomerSummaryResponse,
)
from app.services.user_service import (
    list_admin_customers,
)


router = APIRouter(
    prefix="/admin/customers",
    tags=["Admin - Customers"],
)


@router.get(
    "",
    response_model=list[
        AdminCustomerSummaryResponse
    ],
    status_code=status.HTTP_200_OK,
)
def get_customers(
    q: str | None = Query(
        default=None,
        max_length=100,
    ),
    is_active: bool | None = Query(
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
    return list_admin_customers(
        db,
        query=q,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )