from datetime import datetime

from pydantic import EmailStr
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Text
from enum import Enum

class TaskStatus(str, Enum):
    completed = "completed"
    partially_completed = "partially_completed"
    not_done = "not_done"

class Task(SQLModel, table=True):
    id: int = Field(primary_key = True, index = True)
    description: str
    status: TaskStatus
    estimated_time: datetime

class User(SQLModel, table=True):
    id: int = Field(primary_key=True, index = True)
    username: str
    email: EmailStr
    password_hash: str = Field(sa_column=Column(Text))

