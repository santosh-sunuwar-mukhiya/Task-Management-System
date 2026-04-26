from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.api.dependencies import UserServiceDep
from app.api.schemas.user import UserCreate, UserRead

router = APIRouter(prefix='/user', tags=["User"])

@router.post("/signup", response_model=UserRead)
async def register_user(user: UserCreate, service: UserServiceDep):
    return await service.add(user)

@router.post("/login")
async def login_user(request_form: Annotated[OAuth2PasswordRequestForm, Depends()], service: UserServiceDep):
    token = await service.token(
        request_form.username, request_form.password
    )

    return {
        "token": token,
        "type": "jwt"
    }

@router.patch("/{id}")
async def update_task(id: int):
    pass

@router.delete("/{id}")
async def delete_task(id: int):
    pass