from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.databases.session import get_session
from app.services.task import TaskService
from app.services.user import UserService

SessionDep = Annotated[AsyncSession, Depends(get_session)]

def get_task_service(session: SessionDep):
    return TaskService(session)

def get_user_service(session: SessionDep):
    return UserService(session)

UserServiceDep = Annotated[UserService, Depends(get_user_service)]

TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]