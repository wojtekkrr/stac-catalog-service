from datetime import datetime
from typing import Annotated, Any
from xml.etree.ElementTree import ParseError

from defusedxml.common import DefusedXmlException
from fastapi import APIRouter, HTTPException, Request, status, Query
from pydantic import ValidationError
from shapely.errors import GEOSException

from ..parsing import get_parser, Provider

from .dependencies import CatalogRepositoryDependency


_CONTENT_TYPES: dict[Provider, set[str]] = {
    "skyisnolimit": {"application/json"},
    "spaceisnolimit": {"application/xml", "text/xml"},
}

router = APIRouter()


@router.post(
    "/ingest/{provider}",
)
async def ingest_metadata(
    provider: Provider,
    request: Request,
    repository: CatalogRepositoryDependency,
) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    media_type = content_type.split(";", maxsplit=1)[0].lower()
    if media_type not in _CONTENT_TYPES[provider]:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Nieobsługiwany Content-Type: {media_type}",
        )

    raw_data = await request.body()
    parser = get_parser(provider)
    try:
        item = parser(raw_data)
    except (
        ValidationError,
        ParseError,
        DefusedXmlException,
        GEOSException,
        ValueError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    repository.upsert_item(item)

    return item.to_dict()


@router.get("/search")
def search_items(
    repository: CatalogRepositoryDependency,
    bbox: Annotated[
        str | None,
        Query(description="Format: west,south,east,north"),
    ] = None,
    datetime_filter: Annotated[
        str | None,
        Query(
            alias="datetime",
            description="Data lub przedział STAC, np. start/end",
        ),
    ] = None,
    max_cloud_cover: Annotated[
        float | None,
        Query(ge=0, le=100),
    ] = None,
    product_level: Annotated[
        str | None,
        Query(min_length=1),
    ] = None,
) -> dict[str, Any]:
    query: dict[str, Any] = {}

    if bbox is not None:
        query["bbox"] = _parse_bbox(bbox)

    if datetime_filter is not None:
        _validate_datetime_filter(datetime_filter)
        query["datetime"] = datetime_filter

    property_filters: dict[str, Any] = {}

    if max_cloud_cover is not None:
        property_filters["eo:cloud_cover"] = {
            "lte": max_cloud_cover,
        }

    if product_level is not None:
        property_filters["processing:level"] = {
            "eq": product_level,
        }

    if property_filters:
        query["query"] = property_filters

    return repository.search(query).model_dump(mode="json")


def _parse_bbox(value: str) -> list[float]:
    try:
        bbox = [float(element.strip()) for element in value.split(",")]
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="bbox musi zawierać liczby",
        ) from error

    if len(bbox) != 4:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="bbox musi zawierać cztery wartości",
        )

    return bbox


def _validate_datetime_filter(value: str) -> None:
    elements = value.split("/")
    if len(elements) not in {1, 2}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Niepoprawny format datetime",
        )

    try:
        for element in elements:
            if element != "..":
                _parse_datetime(element)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="datetime musi być zgodny z RFC 3339",
        ) from error


def _parse_datetime(value: str) -> None:
    if "T" not in value:
        raise ValueError("Brak czasu")

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        raise ValueError("Brak strefy czasowej")
