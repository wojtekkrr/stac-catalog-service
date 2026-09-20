from datetime import datetime
from typing import Literal
from xml.etree.ElementTree import Element

from defusedxml import ElementTree
from pydantic import AnyUrl, BaseModel, Field, model_validator
from pyproj import Transformer
import pystac
from shapely import wkt
from shapely.geometry import mapping, Polygon
from shapely.ops import transform

from .stac_extensions import EO_SCHEMA, PROCESSING_SCHEMA


type _BandName = Literal["B04_RED", "B08_NIR"]


_BAND_ASSET_KEYS: dict[_BandName, str] = {
    "B04_RED": "red",
    "B08_NIR": "nir",
}


class _HeaderInfo(BaseModel):
    mission: Literal["SPACE_EYE"]
    spacecraft_id: str
    granule_id: str


class _TemporalCoverage(BaseModel):
    start_time_utc: datetime
    stop_time_utc: datetime


class _ProductQuality(BaseModel):
    processing_level: str
    cloud_coverage_percentage: float = Field(ge=0, le=100)


class _GlobalBoundingBox(BaseModel):
    west_longitude: float
    east_longitude: float
    south_latitude: float
    north_latitude: float

    def as_list(self) -> list[float]:
        return [
            self.west_longitude,
            self.south_latitude,
            self.east_longitude,
            self.north_latitude,
        ]


class _GeometricProperties(BaseModel):
    footprint_wkt: str
    global_bbox: _GlobalBoundingBox


class _RasterBand(BaseModel):
    name: _BandName
    url: AnyUrl


class _RasterFiles(BaseModel):
    bands: tuple[_RasterBand, _RasterBand]
    overview_url: AnyUrl

    @model_validator(mode="after")
    def validate_bands(self) -> "_RasterFiles":
        band_names = {band.name for band in self.bands}

        if band_names != {"B04_RED", "B08_NIR"}:
            raise ValueError("Wymagane jest dokładnie jedno pasmo B04_RED i B08_NIR")

        return self


class _SpaceMetadata(BaseModel):
    header_info: _HeaderInfo
    temporal_coverage: _TemporalCoverage
    product_quality: _ProductQuality
    geometric_properties: _GeometricProperties
    raster_files: _RasterFiles


_XML_NAMESPACE = {
    "ns": "http://spaceisnolimit.com/schemas/metadata/v2",
}


def parse_space_is_no_limit(raw_data: bytes) -> pystac.Item:
    root = ElementTree.fromstring(raw_data)
    metadata = _parse_metadata(root)
    item = _create_stac_item(metadata)
    _add_assets(item, metadata.raster_files)

    return item


def _parse_metadata(root: Element) -> _SpaceMetadata:
    header = _required_element(root, "ns:HeaderInfo")
    temporal = _required_element(root, "ns:TemporalCoverage")
    quality = _required_element(root, "ns:ProductQuality")
    geometry = _required_element(root, "ns:GeometricProperties")
    bbox = _required_element(geometry, "ns:GlobalBBOX")
    raster_files = _required_element(root, "ns:RasterFiles")

    bands = [
        _RasterBand.model_validate(
            {
                "name": _required_attribute(band, "name"),
                "url": _required_text(band, "ns:URL"),
            }
        )
        for band in raster_files.findall("ns:Band", _XML_NAMESPACE)
    ]

    overview = _required_element(raster_files, "ns:OverviewFile")

    return _SpaceMetadata(
        header_info=_HeaderInfo.model_validate(
            {
                "mission": _required_text(header, "ns:Mission"),
                "spacecraft_id": _required_text(header, "ns:SpacecraftID"),
                "granule_id": _required_text(header, "ns:GranuleID"),
            }
        ),
        temporal_coverage=_TemporalCoverage.model_validate(
            {
                "start_time_utc": _required_text(temporal, "ns:StartTimeUTC"),
                "stop_time_utc": _required_text(temporal, "ns:StopTimeUTC"),
            }
        ),
        product_quality=_ProductQuality.model_validate(
            {
                "processing_level": _required_text(
                    quality,
                    "ns:ProcessingLevel",
                ),
                "cloud_coverage_percentage": _required_text(
                    quality,
                    "ns:CloudCoveragePercentage",
                ),
            }
        ),
        geometric_properties=_GeometricProperties.model_validate(
            {
                "footprint_wkt": _required_text(
                    geometry,
                    "ns:FootprintWKT",
                ),
                "global_bbox": {
                    "west_longitude": _required_text(
                        bbox,
                        "ns:WestBoundLongitude",
                    ),
                    "south_latitude": _required_text(
                        bbox,
                        "ns:SouthBoundLatitude",
                    ),
                    "east_longitude": _required_text(
                        bbox,
                        "ns:EastBoundLongitude",
                    ),
                    "north_latitude": _required_text(
                        bbox,
                        "ns:NorthBoundLatitude",
                    ),
                },
            }
        ),
        raster_files=_RasterFiles.model_validate(
            {
                "bands": bands,
                "overview_url": _required_text(overview, "ns:URL"),
            }
        ),
    )


def _create_stac_item(metadata: _SpaceMetadata) -> pystac.Item:
    header = metadata.header_info
    temporal = metadata.temporal_coverage
    quality = metadata.product_quality
    geometry = metadata.geometric_properties

    transformed_geometry = _transform_footprint(
        footprint_wkt=geometry.footprint_wkt,
    )

    item = pystac.Item(
        id=header.granule_id,
        geometry=mapping(transformed_geometry),
        bbox=geometry.global_bbox.as_list(),
        datetime=None,
        start_datetime=temporal.start_time_utc,
        end_datetime=temporal.stop_time_utc,
        properties={
            "platform": header.spacecraft_id,
            "constellation": header.mission,
            "eo:cloud_cover": quality.cloud_coverage_percentage,
            "processing:level": quality.processing_level,
        },
        collection="space-eye",
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
    raster_files: _RasterFiles,
) -> None:
    for band in raster_files.bands:
        asset_key = _BAND_ASSET_KEYS[band.name]

        item.add_asset(
            asset_key,
            pystac.Asset(
                href=str(band.url),
                media_type=pystac.MediaType.TIFF,
                roles=["data"],
            ),
        )
    item.add_asset(
        "quicklook",
        pystac.Asset(
            href=str(raster_files.overview_url),
            media_type=pystac.MediaType.JPEG,
            roles=["thumbnail"],
        ),
    )


def _transform_footprint(
    footprint_wkt: str,
) -> Polygon:
    source_geometry = wkt.loads(footprint_wkt)
    if not isinstance(source_geometry, Polygon):
        raise ValueError(f"Nieobsługiwany typ geometrii: {source_geometry.geom_type}")

    if not source_geometry.is_valid:
        raise ValueError("FootprintWKT zawiera niepoprawną geometrię")

    transformer = Transformer.from_crs(
        "EPSG:32634",
        "OGC:CRS84",
        always_xy=True,
    )

    return transform(
        transformer.transform,
        source_geometry,
    )


def _required_element(parent: Element, path: str) -> Element:
    element = parent.find(path, _XML_NAMESPACE)
    if element is None:
        raise ValueError(f"Brak wymaganego elementu XML: {path}")

    return element


def _required_text(parent: Element, path: str) -> str:
    element = _required_element(parent, path)
    if element.text is None or not element.text.strip():
        raise ValueError(f"Element XML nie zawiera wartości: {path}")

    return element.text.strip()


def _required_attribute(element: Element, name: str) -> str:
    value = element.get(name)
    if value is None or not value.strip():
        raise ValueError(f"Brak wymaganego atrybutu XML: {name}")

    return value.strip()
