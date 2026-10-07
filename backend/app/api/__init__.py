from fastapi import APIRouter

from app.api import admin, ads, complaints, config, me, messages, profile

api_router = APIRouter(prefix="/api")
api_router.include_router(config.router)
api_router.include_router(me.router)
api_router.include_router(profile.router)
api_router.include_router(messages.router)
api_router.include_router(ads.router)
api_router.include_router(complaints.router)
api_router.include_router(admin.router)
