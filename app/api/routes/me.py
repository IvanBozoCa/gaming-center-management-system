from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    get_db,
)
from app.models.time_wallet import TimeWallet
from app.models.user import User
from app.schemas.time_wallet import (
    TimeWalletResponse,
)


router = APIRouter(
    prefix="/me",
    tags=["Me"],
)


@router.get(
    "/wallet",
    response_model=TimeWalletResponse,
)
def get_my_wallet(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(get_db),
):
    wallet = db.scalar(
        select(TimeWallet).where(
            TimeWallet.user_id
            == current_user.id
        )
    )

    if wallet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Time wallet not found",
        )

    return wallet