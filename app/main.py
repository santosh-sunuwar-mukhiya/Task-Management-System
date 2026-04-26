from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from scalar_fastapi import get_scalar_api_reference

from app.api.router import master_router
from app.databases.session import create_db_tables


@asynccontextmanager
async def life_handler(app: FastAPI):
    print("server started and tables are created if they are not created yet.")
    await create_db_tables()
    yield
    print("server stopped.......")

app = FastAPI(lifespan=life_handler)

app.include_router(master_router)

@app.get("/root")
def root():
    return {"message": "Hello World."}

### Scalar API Documentation
@app.get("/scalar", include_in_schema=False)
def get_scalar_docs():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title="Scalar API",
    )