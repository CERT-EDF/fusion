"""Fusion Download API Client"""

from dataclasses import dataclass
from pathlib import Path

from ...concept import PendingDownloadKey
from ...helper.logging import get_logger
from ..impl import FusionClient

_LOGGER = get_logger('client.api.download')


@dataclass(kw_only=True)
class FusionDownloadAPIClient:
    """Fusion Download API Client"""

    fusion_client: FusionClient

    async def download(
        self, pdk: PendingDownloadKey, output: Path
    ) -> Path | None:
        """Download file from server"""
        _LOGGER.info("downloading %s to %s", pdk.guid, output)
        endpoint = f'/api/download/{pdk.guid}/{pdk.token}'
        return await self.fusion_client.download(endpoint, output)
