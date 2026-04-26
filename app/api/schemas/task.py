"""
schemas/task.py

Pydantic schemas — these define the SHAPE of data coming in and going out of the API.
They are NOT database models. They are validation + serialization contracts.

WHY separate schemas from database models?
  - The Task database model has ALL columns (id, description, status, estimated_time)
  - But when CREATING a task, the user should only send `description`
    (status and estimated_time are set by the server as business rules)
  - When READING a task, we want to send back ALL fields including `id`
  - Schemas let us control exactly what goes in and what comes out
    for each operation independently.

SCHEMA HIERARCHY:
  TaskBase       → shared fields (description)
    ├── TaskCreate  → what the client sends when creating (just description)
    └── TaskRead    → what the server sends back (id + description + status + estimated_time)

  TaskUpdate     → what the client sends when updating (all fields optional)
"""

from datetime import datetime
from pydantic import BaseModel, Field
from app.databases.models import TaskStatus


class TaskBase(BaseModel):
    """
    Shared fields across multiple schemas.
    Putting `description` here avoids repeating it in TaskCreate and TaskRead.
    """
    description: str


class TaskCreate(TaskBase):
    """
    Schema for POST /task/ request body.

    The client only sends `description`.
    `status` and `estimated_time` are set by the server (business rules in service).

    Inherits `description` from TaskBase.
    No extra fields needed — `pass` is fine.
    """
    pass


class TaskRead(TaskBase):
    """
    Schema for GET /task/{id} and all other response bodies.

    FIX: Added `id` field — without this, responses were missing the task ID.
    The client needs the ID to make follow-up requests (update, delete).

    This inherits `description` from TaskBase and adds id, status, estimated_time.

    FastAPI uses this as `response_model` to:
      1. Filter out any fields not listed here (e.g., internal fields)
      2. Serialize the Task SQLModel object into JSON
      3. Validate the outgoing data matches this shape
    """
    id: int                       # FIX: was missing, now included in responses
    status: TaskStatus
    estimated_time: datetime

    # This tells Pydantic: "you can build this schema from a SQLModel/ORM object"
    # Without this, Pydantic would only accept plain dicts, not Task objects
    model_config = {"from_attributes": True}


class TaskUpdate(BaseModel):
    """
    Schema for PATCH /task/{id} request body.

    ALL fields are Optional (None by default) because PATCH is partial update.
    The client can send just `status`, just `estimated_time`, or both.

    WHY NOT inherit from TaskBase?
      Because `description` is not updatable in this design.
      If you want to allow updating description, add it here as Optional[str] = None.

    HOW model_dump(exclude_unset=True) uses this:
      - Fields the client did NOT send are "unset" (different from None)
      - exclude_unset=True removes those unset fields from the dict
      - This prevents accidentally overwriting DB values with None
    """
    status: TaskStatus | None = Field(default=None)
    estimated_time: datetime | None = Field(default=None)