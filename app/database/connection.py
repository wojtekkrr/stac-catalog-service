from typing import Any

from psycopg import Connection
from psycopg_pool import ConnectionPool


type _Connection = Connection[tuple[Any, ...]]

type Pool = ConnectionPool[_Connection]


_DATABASE_URL = "postgresql://stac_user:local_stac_password@pgstac:5432/stac_catalog"


def create_connection_pool() -> Pool:
    return ConnectionPool(
        conninfo=_DATABASE_URL,
        min_size=1,
        max_size=10,
        open=False,
    )
