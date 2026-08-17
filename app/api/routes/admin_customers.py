from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from uuid import UUID
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db,
    require_admin,
)
from app.models.user import User
from app.schemas.admin_customer import (
    AdminCustomerSummaryResponse,
    AdminCustomerDetailResponse,
    
)
from app.services.user_service import (
    AdminCustomerNotFoundError,
    AdminCustomerWalletNotFoundError,
    get_admin_customer_detail,
    list_admin_customers,
)
from app.schemas.time_transaction import (
    TimeTransactionResponse,
)
from app.schemas.time_wallet import (
    TimeWalletResponse,
)
from app.services.time_wallet_service import (
    CustomerNotFoundError,
    CustomerWalletNotFoundError,
    get_admin_customer_wallet,
    list_admin_customer_time_transactions,
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


@router.get(
    "/{customer_id}/wallet",
    response_model=TimeWalletResponse,
    status_code=status.HTTP_200_OK,
    summary="Consultar saldo de tiempo de un cliente",
    description=(
    "Devuelve el saldo actual de tiempo disponible "
    "y reservado del cliente, expresado en segundos. "
    "La operación es exclusivamente de lectura."
),
)
def get_customer_wallet(
    customer_id: UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        return get_admin_customer_wallet(
            db,
            customer_id=customer_id,
        )

    except CustomerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        ) from exc

    except CustomerWalletNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer wallet not found",
        ) from exc
    
    
@router.get(
    "/{customer_id}/time-transactions",
    response_model=list[
        TimeTransactionResponse
    ],
    status_code=status.HTTP_200_OK,
    summary="Consultar historial de tiempo de un cliente",
    description=(
        "Devuelve los movimientos del ledger de tiempo "
        "del cliente, ordenados desde el más reciente "
        "al más antiguo por created_at DESC e id DESC. "
        "Los campos available_seconds_delta y "
        "reserved_seconds_delta representan segundos "
        "de tiempo y no valores monetarios. "
        "La operación es exclusivamente de lectura."
    ),
)
def get_customer_time_transactions(
    customer_id: UUID,
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
    try:
        return (
            list_admin_customer_time_transactions(
                db,
                customer_id=customer_id,
                limit=limit,
                offset=offset,
            )
        )

    except CustomerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        ) from exc

    except CustomerWalletNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer wallet not found",
        ) from exc
    


@router.get(
    "/{customer_id}",
    response_model=AdminCustomerDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Consultar detalle de un cliente",
    description=(
        "Devuelve el perfil administrativo y "
        "saldo actual de un cliente registrado. "
        "La operación es exclusivamente de lectura."
    ),
)
def get_customer_detail(
    customer_id: UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    try:
        return get_admin_customer_detail(
            db,
            customer_id=customer_id,
        )

    except AdminCustomerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        ) from exc

    except AdminCustomerWalletNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer wallet not found",
        ) from exc
    

