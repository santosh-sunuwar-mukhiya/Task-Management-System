"""
routers/task.py

The ROUTER LAYER — this handles HTTP concerns ONLY.

RULE: This file should NOT contain business logic or database calls.
      It only knows about: HTTP methods, request/response shapes, HTTP status codes.

WHAT this file is responsible for:
  1. Defining URL paths and HTTP methods (GET, POST, PATCH, DELETE)
  2. Declaring what the REQUEST body looks like  (TaskCreate, TaskUpdate)
  3. Declaring what the RESPONSE body looks like (TaskRead)
  4. Basic HTTP-level validation (e.g., "did the user send an empty body?")
  5. Calling the service and returning its result

WHAT this file is NOT responsible for:
  - Talking to the database directly
  - Business rules (default status, estimated_time logic, etc.)
"""

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import TaskServiceDep
from app.api.schemas.task import TaskRead, TaskCreate, TaskUpdate

# ---------------------------------------------------------------------------
# A NOTE ON SCHEMAS IN THE ROUTER vs THE SERVICE:
#
# TaskCreate / TaskUpdate are used in BOTH the router and service, but
# for different reasons:
#
#   ROUTER:
#     - Uses them as TYPE ANNOTATIONS on function parameters.
#     - FastAPI reads these annotations and automatically:
#         1. Parses the JSON request body into the schema object
#         2. Validates it (required fields, field types, constraints)
#         3. Returns 422 Unprocessable Entity automatically if validation fails
#     - The router does NOT call .model_dump() on them (mostly) —
#       it just passes the schema object to the service.
#
#   SERVICE:
#     - Receives the already-validated schema object from the router.
#     - Uses .model_dump() to extract a dict when it needs to apply
#       the data to a database model (e.g., for sqlmodel_update()).
#
#   TaskRead:
#     - Only used in the ROUTER as the `response_model`.
#     - FastAPI uses it to filter/serialize the returned data.
#     - The service never needs to know about TaskRead.
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/task", tags=["Task"])


# -----------------------------------------------------------------------
# GET /task/{id}
# -----------------------------------------------------------------------
@router.get("/{id}", response_model=TaskRead)
async def get_task(id: int, service: TaskServiceDep):
    """
    Fetch a single task by its ID.

    `id` comes from the URL path: GET /task/5  →  id=5
    `service` is injected by FastAPI via TaskServiceDep (dependency injection).

    response_model=TaskRead tells FastAPI:
      - "Filter the returned object through TaskRead before sending to the client"
      - This means even if the Task object has extra internal fields,
        only the fields defined in TaskRead are sent in the response.

    FIX: TaskRead now includes `id` so the client gets back all fields.
    (See schemas/task.py — TaskRead was missing `id` originally)
    """
    # service.get() is defined in services/task.py
    # It calls self.session.get(Task, id) internally — a SQLAlchemy method
    # that runs SELECT * FROM task WHERE id = ?
    # If not found, service.get() raises 404 automatically
    task = await service.get(id)
    return task


# -----------------------------------------------------------------------
# POST /task/
# -----------------------------------------------------------------------
@router.post("/", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def add_task(task_create: TaskCreate, service: TaskServiceDep):
    """
    Create a new task.

    `task_create: TaskCreate` — FastAPI reads the request JSON body and
    validates it as a TaskCreate object. If the body is missing or has
    wrong types, FastAPI returns 422 automatically before this function runs.

    BUG FIXED: Original route was @router.post("/task") which combined with
    the router prefix "/task" created the URL "/task/task". Changed to "/".

    HOW task_create flows through the system:
      Router receives JSON:  {"description": "Buy milk"}
        → FastAPI creates:   TaskCreate(description="Buy milk")
        → Router passes to:  service.add(task_create)
        → Service calls:     task_create.model_dump()
                             → {"description": "Buy milk"}
        → Service creates:   Task(description="Buy milk", status="not_done", ...)
        → Service inserts into DB and returns the Task object
        → Router returns it, filtered through TaskRead
    """
    task = await service.add(task_create)
    return task


# -----------------------------------------------------------------------
# PATCH /task/{id}
# -----------------------------------------------------------------------
@router.patch("/{id}", response_model=TaskRead)
async def update_task(id: int, update_data: TaskUpdate, service: TaskServiceDep):
    """
    Partially update a task (status and/or estimated_time).

    WHY we check for empty body HERE in the router (not in the service):
      - "Did the client send any data?" is an HTTP concern.
      - Sending a PATCH with an empty body is a client-side mistake → HTTP 400.
      - This is the only model_dump() call that belongs in the router.

    HOW model_dump(exclude_unset=True) WORKS for the empty-body check:
      - If client sends:    {}  (empty body)
        update_data becomes: TaskUpdate(status=None, estimated_time=None)
        .model_dump(exclude_unset=True) → {}  (empty dict — no fields were set)
        `if not empty_check` → True → raise 400

      - If client sends:    {"status": "completed"}
        update_data becomes: TaskUpdate(status="completed", estimated_time=None)
        .model_dump(exclude_unset=True) → {"status": "completed"}
        `if not empty_check` → False → proceed to service

    IMPORTANT: We do NOT pass this dict to the service.
    We pass the full `update_data` schema object to the service.
    The service calls model_dump(exclude_unset=True) again internally
    when it needs to apply the data to the Task object via sqlmodel_update().
    This keeps the service in control of how it uses the data.
    """
    # HTTP-level guard: reject empty PATCH requests
    empty_check = update_data.model_dump(exclude_unset=True)
    if not empty_check:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No data provided to update. Please send at least one field."
        )

    # Pass the full schema object to the service — NOT the dict
    # The service will call .model_dump(exclude_unset=True) itself
    updated_task = await service.update(id, update_data)
    return updated_task


# -----------------------------------------------------------------------
# DELETE /task/{id}
# -----------------------------------------------------------------------
@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(id: int, service: TaskServiceDep):
    """
    Delete a task by ID.

    Returns HTTP 204 No Content on success (standard REST convention for DELETE).
    If the task doesn't exist, service.delete() raises 404.

    Note: We return None (no body) because HTTP 204 means "success, no content".
    """
    await service.delete(id)
    # No return statement = FastAPI returns 204 No Content automatically