"""
services/task.py

The SERVICE LAYER — this is where ALL business logic lives.

RULE: This file should never know about HTTP (no status codes, no Request/Response).
      It only knows about: database operations, business rules, and data shapes.

WHY a service layer exists:
  - Routers handle HTTP concerns (what came in, what goes out)
  - Services handle business concerns (how to create a task, what rules apply)
  - This separation means you can test business logic without starting FastAPI
"""

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.task import TaskCreate, TaskUpdate
from app.databases.models import Task, TaskStatus
# from app.core.exceptions import EntityNotFound   # <-- you should create this (see Future Work below)

# ---------------------------------------------------------------------------
# A NOTE ON IMPORTS:
# We import TaskCreate and TaskUpdate from schemas here because the service
# receives those objects from the router. The service is the "consumer" of
# the validated request data that the router already parsed.
# ---------------------------------------------------------------------------


class TaskService:
    """
    TaskService owns all task-related database operations and business logic.

    It receives a session in __init__ and stores it as self.session.
    Every method uses self.session to talk to the database.
    """

    def __init__(self, session: AsyncSession):
        # self.session is the SQLAlchemy AsyncSession object.
        # It was created by get_session() in databases/session.py,
        # and injected here via FastAPI's dependency injection chain:
        #   get_session() → SessionDep → get_task_service(session) → TaskService(session)
        self.session = session

    # -----------------------------------------------------------------------
    # GET
    # -----------------------------------------------------------------------
    async def get(self, id: int) -> Task:
        """
        Fetch a single Task from the database by its primary key (id).

        HOW self.session.get() WORKS:
          - self.session is a SQLAlchemy AsyncSession
          - .get(Model, primary_key) is a SQLAlchemy method — NOT FastAPI, NOT Python builtin
          - It runs: SELECT * FROM task WHERE id = <id> LIMIT 1
          - Returns the Task object if found, or None if not found
          - It also checks SQLAlchemy's identity map (in-memory cache) first
            before hitting the database, so it's efficient for repeated calls.

        WHY we raise the "not found" error HERE (in the service) and not in the router:
          - "Does this task exist?" is a BUSINESS rule, not an HTTP rule.
          - The router simply receives the result. If it's None, that's the service's problem.
          - This also means if you ever call service.get() from another service,
            you automatically get the same "not found" protection.
        """
        # self.session.get() is an ASYNC method — must use `await`
        # BUG FIXED: original code was missing `await` on session.get() in update() and delete()
        task = await self.session.get(Task, id)

        if not task:
            # Raise a custom exception (see core/exceptions.py in Future Work)
            # For now you can raise HTTPException here, but ideally move it to a
            # custom exception class so the service stays HTTP-agnostic.
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with id #{id} does not exist."
            )

        return task

    # -----------------------------------------------------------------------
    # ADD
    # -----------------------------------------------------------------------
    async def add(self, task_create: TaskCreate) -> Task:
        """
        Create a new Task in the database.

        PARAMETER: task_create: TaskCreate
          - This is a Pydantic schema object (from api/schemas/task.py)
          - FastAPI already validated it before passing to the router,
            and the router passes it here unchanged.
          - We use it here to build the actual Task SQLModel object.

        HOW model_dump() WORKS:
          - task_create.model_dump() converts the Pydantic object into a plain Python dict.
          - Example: TaskCreate(description="Buy milk")
                     → {"description": "Buy milk"}
          - We then use **dict to unpack it as keyword arguments into Task(...)
          - This is equivalent to: Task(description=task_create.description)
          - model_dump() is a PYDANTIC method — not FastAPI, not SQLAlchemy.
        """
        # Build the Task SQLModel instance.
        # task_create only has `description` (from TaskBase).
        # We add `status` and `estimated_time` here — these are BUSINESS RULES,
        # not things the user should provide when creating a task.
        new_task = Task(
            **task_create.model_dump(),         # unpacks → description="..."
            status=TaskStatus.not_done,         # business rule: new tasks start as not_done
            estimated_time=datetime.now() + timedelta(days=3)  # business rule: 3 days from now
        )

        # --- Three-step database write pattern (always in this order) ---

        # Step 1: session.add() — tells SQLAlchemy "track this object"
        #   - Does NOT write to the database yet
        #   - SQLAlchemy adds it to the "pending" list in the current session
        #   - It's a SYNCHRONOUS method (no await needed)
        self.session.add(new_task)

        # Step 2: await session.commit() — writes to the database
        #   - Executes: INSERT INTO task (description, status, estimated_time) VALUES (...)
        #   - ASYNC method — must use `await`
        await self.session.commit()

        # Step 3: await session.refresh() — re-fetches the row from the database
        #   - After commit, the DB assigns the auto-generated `id`
        #   - Without refresh(), new_task.id would still be None in memory
        #   - This runs: SELECT * FROM task WHERE id = <new_id>
        #   - ASYNC method — must use `await`
        await self.session.refresh(new_task)

        return new_task

    # -----------------------------------------------------------------------
    # UPDATE
    # -----------------------------------------------------------------------
    async def update(self, id: int, update_data: TaskUpdate) -> Task:
        """
        Update an existing Task in the database.

        PARAMETER: update_data: TaskUpdate
          - We receive the full TaskUpdate schema object from the router.
          - We do NOT receive a plain dict here — the router passes the schema object.
          - We call .model_dump() ourselves here in the service when we need the dict.

        HOW sqlmodel_update() WORKS:
          - It's a SQLModel method (not SQLAlchemy, not FastAPI, not Python builtin)
          - Signature: task.sqlmodel_update(data)  where data can be a dict OR a Pydantic model
          - What it does internally:
              for field, value in data.items():
                  setattr(task, field, value)   # same as: task.status = value
          - It MUTATES the task object in place — it does not return anything
          - After calling it, the task object has the new values in memory,
            but NOT yet in the database (you still need add + commit)

        HOW model_dump(exclude_unset=True) WORKS:
          - exclude_unset=True means: "only include fields the user actually sent"
          - Example: user sends {"status": "completed"}
              TaskUpdate(**body) → TaskUpdate(status="completed", estimated_time=None)
              .model_dump()                  → {"status": "completed", "estimated_time": None}
              .model_dump(exclude_unset=True) → {"status": "completed"}
          - Without exclude_unset=True, you'd overwrite estimated_time with None
            even though the user didn't intend to change it — BUG!
          - We pass this dict to sqlmodel_update() so only the provided fields are applied.

        BUG FIXED:
          - Original code was missing `await` on self.session.get(Task, id)
          - session.get() is async; calling it without await returns a coroutine object,
            not a Task — so `if not task` was always False (coroutine is truthy!),
            and then sqlmodel_update() was called on a coroutine, causing the error.
        """
        # BUG FIXED: added `await` — session.get() is async
        task = await self.session.get(Task, id)

        if not task:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with id #{id} does not exist."
            )

        # model_dump(exclude_unset=True) → only fields the user actually provided
        # This is the correct place to call model_dump() — in the service,
        # just before applying to the database object.
        update_dict = update_data.model_dump(exclude_unset=True)

        # sqlmodel_update() applies the dict to the task object in memory
        # It sets task.status and/or task.estimated_time based on what's in update_dict
        task.sqlmodel_update(update_dict)   # for key, value in update_dict.items():
                                                # setattr(task, key, value)

        # Persist changes to the database (same 3-step pattern as add)
        self.session.add(task)       # mark as "dirty" (has changes to write)
        await self.session.commit()  # run: UPDATE task SET ... WHERE id = <id>
        await self.session.refresh(task)  # re-fetch to get the final DB state

        return task

    # -----------------------------------------------------------------------
    # DELETE
    # -----------------------------------------------------------------------
    async def delete(self, id: int) -> None:
        """
        Delete a Task from the database by id.

        BUG FIXED: added `await` on self.session.get(Task, id)
        Same problem as update() — without await, task is a coroutine (always truthy),
        and session.delete() would receive a coroutine object, not a Task, causing a crash.
        """
        # BUG FIXED: added `await`
        task = await self.session.get(Task, id)

        if not task:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with id #{id} does not exist."
            )

        # session.delete() marks the object for deletion
        # The actual DELETE query runs on commit()
        await self.session.delete(task)
        await self.session.commit()
        # No refresh needed after delete — the object is gone