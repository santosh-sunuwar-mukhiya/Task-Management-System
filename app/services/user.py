from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, status
from pydantic import EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.user import UserCreate
from app.config import security_settings
from app.databases.models import User

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

import jwt

_password_hash = PasswordHash((Argon2Hasher(),))


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, user_create: UserCreate) -> User:
        user = User(
            **user_create.model_dump(exclude=["password"]),
            password_hash=_password_hash.hash(user_create.password)
        )

        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)

        return user

    async def token(self, email: EmailStr, password: str) -> str:
        result = await self.session.execute(select(User).where(User.email == email))

        user = result.scalar()

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email or Password is Wrong",
            )

        try:
            password_is_correct = _password_hash.verify(password, user.password_hash)

        except Exception:
            # Any error during verification = treat as wrong password
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email or Password is incorrect.",
            )

        if not password_is_correct:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email or Password is incorrect.",
            )

        token = jwt.encode(
            payload={
                "user": {
                    "name": user.username,
                    "email": user.email,
                },
                "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            },
            algorithm=security_settings.JWT_ALGORITHM,
            key=security_settings.JWT_SECRET,
        )

        return token
