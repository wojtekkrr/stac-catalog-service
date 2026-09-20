from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl
import pystac

from .stac_extensions import EO_SCHEMA, PROCESSING_SCHEMA


class _AcquisitionMetadata(BaseModel):
    mission_name: Literal["SKY_SHIELD"]
    satellite_id: str
    scene_identifier: str
    capture_timestamp_utc: datetime


class _ProductMetrics(BaseModel):
    cloud_cover_percentage: float = Field(ge=0, le=100)


class _ProductCharacteristics(BaseModel):
    processing_level: str
    metrics: _ProductMetrics


class _PolygonGeometry(BaseModel):
    type: Literal["Polygon"]
    coordinates: list[list[tuple[float, float]]]


class _BoundingBox(BaseModel):
    min_longitude: float
    min_latitude: float
    max_longitude: float
    max_latitude: float

    def as_list(self) -> list[float]:
        return [
            self.min_longitude,
            self.min_latitude,
            self.max_longitude,
            self.max_latitude,
        ]


class _SpatialExtent(BaseModel):
    bounding_box: _BoundingBox
    geometry_geojson: _PolygonGeometry


class _ImageBands(BaseModel):
    red: HttpUrl
    green: HttpUrl
    blue: HttpUrl
    nir: HttpUrl


class _DataDeliverables(BaseModel):
    image_bands: _ImageBands
    thumbnail: HttpUrl


class _SkyMetadata(BaseModel):
    acquisition_metadata: _AcquisitionMetadata
    product_characteristics: _ProductCharacteristics
    spatial_extent: _SpatialExtent
    data_deliverables: _DataDeliverables


def parse_sky_is_no_limit(raw_data: bytes) -> pystac.Item:
    metadata = _SkyMetadata.model_validate_json(raw_data)
    item = _create_stac_item(metadata)
    _add_assets(item, metadata.data_deliverables)

    return item


def _create_stac_item(metadata: _SkyMetadata) -> pystac.Item:
    acquisition = metadata.acquisition_metadata
    product = metadata.product_characteristics
    spatial = metadata.spatial_extent

    item = pystac.Item(
        id=acquisition.scene_identifier,
        geometry=spatial.geometry_geojson.model_dump(mode="json"),
        bbox=spatial.bounding_box.as_list(),
        datetime=acquisition.capture_timestamp_utc,
        properties={
            "platform": acquisition.satellite_id,
            "constellation": acquisition.mission_name,
            "eo:cloud_cover": product.metrics.cloud_cover_percentage,
            "processing:level": product.processing_level,
        },
        collection="sky-shield",
    )

    item.stac_extensions.extend(
        [
            EO_SCHEMA,
            PROCESSING_SCHEMA,
        ]
    )

    return item


def _add_assets(
    item: pystac.Item,
    deliverables: _DataDeliverables,
) -> None:
    image_bands = deliverables.image_bands.model_dump(mode="json")
    for band_name, href in image_bands.items():
        item.add_asset(
            band_name,
            pystac.Asset(
                href=str(href),
                media_type=pystac.MediaType.TIFF,
                roles=["data"],
            ),
        )

    item.add_asset(
        "thumbnail",
        pystac.Asset(
            href=str(deliverables.thumbnail),
            media_type=pystac.MediaType.PNG,
            roles=["thumbnail"],
        ),
    )
