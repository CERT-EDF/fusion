"""Fusion Constant API Client"""

from dataclasses import dataclass

from ...concept import Concept, ConceptType
from ...helper.logging import get_logger
from ..impl import FusionClient

_LOGGER = get_logger('client.api.constant')


@dataclass(kw_only=True)
class FusionConstantAPIClient:
    """Fusion Constant API Client"""

    constant_cls: ConceptType
    fusion_client: FusionClient

    async def constant(self) -> Concept | None:
        """Download file from server"""
        _LOGGER.info("retrieving api constant")
        endpoint = '/api/constant'
        return await self.fusion_client.get(
            endpoint, concept_cls=self.constant_cls
        )
