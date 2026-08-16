from fastapi import FastAPI
from app.api.routes.admin_stations import (
    router as admin_stations_router,
)
from app.api.routes.admin_sessions import (
    router as admin_sessions_router,
)
from app.api.routes.auth import router as auth_router
from app.api.routes.me import router as me_router
from app.api.routes.admin import (
    router as admin_router,
)

app = FastAPI(
    title="Gaming Center Management System API",
    version="0.1.0",
)

app.include_router(auth_router)
app.include_router(me_router)
app.include_router(admin_router)
app.include_router(admin_stations_router)
app.include_router(admin_sessions_router)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "gaming-center-api",
    }