import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.config import get_settings
from app.services.scheduler import scheduler_loop

MEDIA_DIR = Path(__file__).resolve().parent.parent / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
(MEDIA_DIR / "profiles").mkdir(parents=True, exist_ok=True)
(MEDIA_DIR / "splashes").mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    stop = asyncio.Event()
    task = asyncio.create_task(scheduler_loop(stop, interval_seconds=60.0))
    try:
        yield
    finally:
        stop.set()
        await task


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Italian Dreamers API", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "environment": settings.environment}

    return app


app = create_app()
