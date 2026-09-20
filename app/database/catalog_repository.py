from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError
import pystac
from psycopg.types.json import Jsonb

from .connection import Pool


class _StacSearchResult(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    type: Literal["FeatureCollection"]
    features: list[dict[str, Any]]
    links: list[dict[str, Any]]


class _InvalidCatalogResponseError(RuntimeError):
    pass


class CatalogRepository:
    def __init__(self, pool: Pool) -> None:
        self._pool = pool

    def upsert_collection(self, collection: pystac.Collection) -> None:
        content = collection.to_dict()

        with self._pool.connection() as connection:
            connection.execute(
                "SELECT pgstac.upsert_collection(%s)",
                (Jsonb(content),),
            )

    def upsert_item(self, item: pystac.Item) -> None:
        content = item.to_dict()

        with self._pool.connection() as connection:
            connection.execute(
                "SELECT pgstac.upsert_item(%s)",
                (Jsonb(content),),
            )

    def search(self, query: dict[str, Any]) -> _StacSearchResult:
        with self._pool.connection() as connection:
            row = connection.execute(
                "SELECT pgstac.search(%s)",
                (Jsonb(dict(query)),),
            ).fetchone()

        if row is None:
            raise _InvalidCatalogResponseError("pgSTAC nie zwrócił odpowiedzi")

        try:
            return _StacSearchResult.model_validate(row[0])
        except ValidationError as error:
            raise _InvalidCatalogResponseError(
                "pgSTAC zwrócił niepoprawną odpowiedź"
            ) from error
