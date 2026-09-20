from collections.abc import Callable
from typing import Literal

import pystac

from .sky_is_no_limit import parse_sky_is_no_limit
from .space_is_no_limit import parse_space_is_no_limit

type Provider = Literal["skyisnolimit", "spaceisnolimit"]

type _MetadataParser = Callable[[bytes], pystac.Item]

_PARSERS: dict[Provider, _MetadataParser] = {
    "skyisnolimit": parse_sky_is_no_limit,
    "spaceisnolimit": parse_space_is_no_limit,
}


def get_parser(provider: Provider) -> _MetadataParser:
    return _PARSERS[provider]
