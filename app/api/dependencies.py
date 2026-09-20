from typing import Annotated, cast

from fastapi import Depends, Request

from ..database import CatalogRepository


def _get_catalog_repository(request: Request) -> CatalogRepository:
    return cast(
        CatalogRepository,
        request.app.state.catalog_repository,
    )


CatalogRepositoryDependency = Annotated[
    CatalogRepository,
    Depends(_get_catalog_repository),
]
