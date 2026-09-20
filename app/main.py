from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import router
from .database import (
    CatalogRepository,
    create_connection_pool,
    initialize_catalog,
)


@asynccontextmanager
async def _lifespan(application: FastAPI) -> AsyncIterator[None]:
    pool = create_connection_pool()
    pool.open(wait=True)

    repository = CatalogRepository(pool)
    initialize_catalog(repository)

    application.state.catalog_repository = repository

    try:
        yield
    finally:
        pool.close()


app = FastAPI(
    title="STAC Catalog Service",
    version="0.1.0",
    lifespan=_lifespan,
)

app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
