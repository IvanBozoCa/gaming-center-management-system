from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.me import router as me_router


app = FastAPI(
    title="Gaming Center Management System API",
    version="0.1.0",
)


app.include_router(auth_router)
app.include_router(me_router)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "gaming-center-api",
    }