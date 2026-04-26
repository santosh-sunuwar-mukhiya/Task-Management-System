from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    username: str

class UserRead(UserBase):
    id: int
    email: EmailStr

class UserCreate(UserBase):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    username: str | None = Field(default=None)

