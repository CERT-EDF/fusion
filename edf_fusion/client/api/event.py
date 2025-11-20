"""Fusion Event API Client"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

from ...concept import Event
from ...helper.logging import get_logger
from ..impl import FusionClient

_LOGGER = get_logger('client.api.event')


@dataclass(kw_only=True)
class FusionEventAPIClient:
    """Fusion Event API Client"""

    fusion_client: FusionClient

    async def subscribe(self, case_guid: UUID) -> AsyncIterator[Event]:
        """Download file from server"""
        _LOGGER.info("subscribing to case %s", case_guid)
        endpoint = f'/api/events/case/{case_guid}'
        async for event in self.fusion_client.sse(endpoint, concept_cls=Event):
            yield event
