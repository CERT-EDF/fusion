"""Fusion Info API Client"""

from dataclasses import dataclass

from ...concept import Info
from ...helper.logging import get_logger
from ..impl import FusionClient

_LOGGER = get_logger('client.api.info')


@dataclass(kw_only=True)
class FusionInfoAPIClient:
    """Fusion Info API Client"""

    fusion_client: FusionClient

    async def info(self) -> Info | None:
        """Download file from server"""
        _LOGGER.info("retrieving api info")
        endpoint = '/api/info'
        return await self.fusion_client.get(endpoint, concept_cls=Info)
