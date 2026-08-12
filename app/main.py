from fastapi import FastAPI


app = FastAPI(
    title="Gaming Center Management System API",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "gaming-center-api",
    }