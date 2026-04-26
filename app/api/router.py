from fastapi import APIRouter

from app.api.routers import task, user

master_router = APIRouter()

master_router.include_router(task.router)
master_router.include_router(user.router)
