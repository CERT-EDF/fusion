"""Fusion Constant API"""

from dataclasses import dataclass

from aiohttp.web import Application, Request, Response, get

from ...concept import Concept, ConceptType
from ...helper.aiohttp import json_response
from ...helper.logging import get_logger
from ..auth import Action, get_fusion_auth_api
from .config import FusionConstantAPIConfig

_LOGGER = get_logger('server.constant.impl')
_FUSION_CONST_API = 'fusion_const_api'


@dataclass(kw_only=True)
class FusionConstantAPI:
    """Fusion Constant API"""

    config: FusionConstantAPIConfig
    constant_cls: ConceptType
    _cached_mtime: int = 0
    _cached_constant: Concept | None = None

    def setup(self, webapp: Application):
        """Setup web application routes"""
        _LOGGER.info("install constant api...")
        webapp[_FUSION_CONST_API] = self
        webapp.add_routes(
            [
                get('/api/constant', self.retrieve_constant),
            ]
        )
        if not self.config.constant_path.is_file():
            _LOGGER.warning(
                "constant file not found: %s", self.config.constant_path
            )
        _LOGGER.info("constant api installed.")

    @property
    def cached_constant(self) -> Concept | None:
        """Cached constant"""
        if not self.config.constant_path.is_file():
            return None
        mtime = int(self.config.constant_path.stat().st_mtime)
        if mtime > self._cached_mtime:
            _LOGGER.info("reloading %s", self.config.constant_path)
            self._cached_mtime = mtime
            self._cached_constant = self.constant_cls.from_filepath(
                self.config.constant_path
            )
        return self._cached_constant

    async def retrieve_constant(self, request: Request) -> Response:
        """Handle client request for constant"""
        if self.config.auth_required:
            fusion_auth_api = get_fusion_auth_api(request)
            action = Action(name='retrieve_constant')
            await fusion_auth_api.authorize(request, action)
        cached_constant = self.cached_constant
        if not cached_constant:
            return json_response(status=503, message="Missing constant file")
        return json_response(data=cached_constant.to_dict())


def get_fusion_const_api(request: Request) -> FusionConstantAPI:
    """Retrieve FusionInfoAPI instance from request"""
    return request.app[_FUSION_CONST_API]
