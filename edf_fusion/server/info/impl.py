"""Fusion Info API"""

from dataclasses import dataclass

from aiohttp.web import Application, Request, Response, get

from ...concept import Info
from ...helper.aiohttp import json_response
from ...helper.logging import get_logger
from ..auth import Action, get_fusion_auth_api
from .config import FusionInfoAPIConfig

_LOGGER = get_logger('server.info.impl')
_FUSION_INFO_API = 'fusion_info_api'


@dataclass(kw_only=True)
class FusionInfoAPI:
    """Fusion Info API"""

    info: Info
    config: FusionInfoAPIConfig

    def setup(self, webapp: Application):
        """Setup web application routes"""
        _LOGGER.info("install info api...")
        webapp[_FUSION_INFO_API] = self
        webapp.add_routes(
            [
                get('/api/info', self.retrieve_info),
            ]
        )
        _LOGGER.info("info api installed.")

    async def retrieve_info(self, request: Request) -> Response:
        """Handle client request for info"""
        if self.config.auth_required:
            fusion_auth_api = get_fusion_auth_api(request)
            action = Action(name='retrieve_info')
            await fusion_auth_api.authorize(request, action)
        return json_response(data=self.info.to_dict())


def get_fusion_info_api(request: Request) -> FusionInfoAPI:
    """Retrieve FusionInfoAPI instance from request"""
    return request.app[_FUSION_INFO_API]
