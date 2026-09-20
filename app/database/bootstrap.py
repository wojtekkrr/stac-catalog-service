from datetime import datetime

import pystac

from .catalog_repository import CatalogRepository


def initialize_catalog(repository: CatalogRepository) -> None:
    """Tworzy lub aktualizuje kolekcje STAC obsługiwanych misji."""
    temporal_intervals: list[list[datetime | None]] = [[None, None]]

    extent = pystac.Extent(
        spatial=pystac.SpatialExtent([[-180.0, -90.0, 180.0, 90.0]]),
        temporal=pystac.TemporalExtent(temporal_intervals),
    )

    collections = (
        pystac.Collection(
            id="sky-shield",
            description="Produkty misji SKY_SHIELD",
            extent=extent,
            license="proprietary",
        ),
        pystac.Collection(
            id="space-eye",
            description="Produkty misji SPACE_EYE",
            extent=extent,
            license="proprietary",
        ),
    )

    for collection in collections:
        repository.upsert_collection(collection)
