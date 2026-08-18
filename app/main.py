from fastapi import FastAPI
from app.api.routes.admin_stations import (
    router as admin_stations_router,
)
from app.api.routes.admin_sessions import (
    router as admin_sessions_router,
)
from app.api.routes.admin_customers import (
    router as admin_customers_router,
)
from app.api.routes.auth import router as auth_router
from app.api.routes.me import router as me_router
from app.api.routes.admin import (
    router as admin_router,
)
from app.api.routes.admin_guest_sessions import (
    router as admin_guest_sessions_router,
)
from app.api.routes.admin_time_products import (
    router as admin_time_products_router,
)
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(
    title="Gaming Center Management System API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(me_router)
app.include_router(admin_router)
app.include_router(admin_customers_router)
app.include_router(admin_stations_router)
app.include_router(admin_sessions_router)
app.include_router(admin_guest_sessions_router)
app.include_router(admin_time_products_router)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "gaming-center-api",
    }