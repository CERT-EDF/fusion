"""Fusion Case API"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from aiohttp.web import Application, Request, Response, delete, get, post, put

from ...concept import Case, CaseType
from ...helper.aiohttp import get_guid, get_json_body, json_response
from ...helper.logging import get_logger
from ..auth import get_fusion_auth_api
from .config import FusionCaseAPIConfig
from .context import (
    AttachContext,
    CreateContext,
    DeleteContext,
    EnumerateContext,
    RetrieveContext,
    UpdateContext,
)

_LOGGER = get_logger('server.case.impl')
_FUSION_CASE_API = 'fusion_case_api'


@dataclass(kw_only=True)
class FusionCaseAPI:
    """Fusion Case API"""

    config: FusionCaseAPIConfig
    case_cls: CaseType
    attach_case_impl: Callable[[AttachContext], Awaitable[Case | None]]
    create_case_impl: Callable[[CreateContext], Awaitable[Case | None]]
    update_case_impl: Callable[[UpdateContext], Awaitable[Case | None]]
    delete_case_impl: Callable[[DeleteContext], Awaitable[bool]]
    retrieve_case_impl: Callable[[RetrieveContext], Awaitable[Case | None]]
    enumerate_cases_impl: Callable[[EnumerateContext], Awaitable[list[Case]]]

    def setup(self, webapp: Application):
        """Setup web application routes"""
        _LOGGER.info("install case api...")
        webapp[_FUSION_CASE_API] = self
        webapp.add_routes(
            [
                get('/api/cases', self.enumerate_cases),
                get('/api/case/{case_guid}', self.retrieve_case),
                put('/api/case/{case_guid}', self.update_case),
                delete('/api/case/{case_guid}', self.delete_case),
                put(
                    '/api/case/{case_guid}/attach/{next_case_guid}',
                    self.attach_case,
                ),
                post('/api/case', self.create_case),
            ]
        )
        _LOGGER.info("case api installed.")

    async def attach_case(self, request: Request) -> Response:
        """Attach case"""
        fusion_auth_api = get_fusion_auth_api(request)
        case_guid = get_guid(request, 'case_guid')
        next_case_guid = get_guid(request, 'next_case_guid')
        if not case_guid or not next_case_guid:
            return json_response(status=400, message="Invalid GUID")
        identity = await fusion_auth_api.authorize(
            request,
            'attach_case',
            context={'case_guid': case_guid, 'next_case_guid': next_case_guid},
        )
        ctx = AttachContext(
            request=request,
            identity=identity,
            case_guid=case_guid,
            next_case_guid=next_case_guid,
        )
        if not ctx.managed:
            return json_response(status=403, message="Fusion Server Only")
        case = await self.attach_case_impl(ctx)
        if not case:
            return json_response(status=400, message="Invalid case")
        return json_response(data=case.to_dict())

    async def create_case(self, request: Request) -> Response:
        """Create a case"""
        fusion_auth_api = get_fusion_auth_api(request)
        identity = await fusion_auth_api.authorize(request, 'create_case')
        body = await get_json_body(request)
        if not isinstance(body, dict):
            return json_response(status=400, message="Invalid body")
        ctx = CreateContext(request=request, identity=identity, body=body)
        case = await self.create_case_impl(ctx)
        if not case:
            return json_response(status=400, message="Invalid case")
        return json_response(data=case.to_dict())

    async def update_case(self, request: Request) -> Response:
        """Update an existing case"""
        fusion_auth_api = get_fusion_auth_api(request)
        case_guid = get_guid(request, 'case_guid')
        if not case_guid:
            return json_response(status=400, message="Invalid GUID")
        identity = await fusion_auth_api.authorize(
            request,
            'update_case',
            context={'case_guid': case_guid},
        )
        body = await get_json_body(request)
        if not isinstance(body, dict):
            return json_response(status=400, message="Invalid body")
        ctx = UpdateContext(
            request=request, identity=identity, body=body, case_guid=case_guid
        )
        case = await self.update_case_impl(ctx)
        if not case:
            return json_response(status=400, message="Invalid case")
        return json_response(data=case.to_dict())

    async def delete_case(self, request: Request) -> Response:
        """Delete an existing case"""
        fusion_auth_api = get_fusion_auth_api(request)
        case_guid = get_guid(request, 'case_guid')
        if not case_guid:
            return json_response(status=400, message="Invalid GUID")
        identity = await fusion_auth_api.authorize(
            request,
            'delete_case',
            context={'case_guid': case_guid, 'is_delete_op': True},
        )
        ctx = DeleteContext(
            request=request, identity=identity, case_guid=case_guid
        )
        deleted = await self.delete_case_impl(ctx)
        if not deleted:
            return json_response(status=400, message="Not deleted")
        return json_response()

    async def retrieve_case(self, request: Request) -> Response:
        """Retrieve case information"""
        fusion_auth_api = get_fusion_auth_api(request)
        case_guid = get_guid(request, 'case_guid')
        if not case_guid:
            return json_response(status=400, message="Invalid GUID")
        identity = await fusion_auth_api.authorize(
            request,
            'retrieve_case',
            context={'case_guid': case_guid},
        )
        ctx = RetrieveContext(
            request=request, identity=identity, case_guid=case_guid
        )
        case = await self.retrieve_case_impl(ctx)
        if not case:
            return json_response(status=404, message="Case not found")
        return json_response(data=case.to_dict())

    async def enumerate_cases(self, request: Request) -> Response:
        """Enumerate cases"""
        fusion_auth_api = get_fusion_auth_api(request)
        identity = await fusion_auth_api.authorize(request, 'enumerate_cases')
        ctx = EnumerateContext(request=request, identity=identity)
        cases = await self.enumerate_cases_impl(ctx)
        data = [
            case.to_dict()
            for case in cases
            if fusion_auth_api.can_access_case(identity, case)
        ]
        return json_response(data=data)


def get_fusion_case_api(request: Request) -> FusionCaseAPI:
    """Retrieve FusionAuthAPI instance from request"""
    return request.app[_FUSION_CASE_API]
