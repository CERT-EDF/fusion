"""Fusion Auth API Implementation"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import cached_property
from json import JSONDecodeError

from aiohttp.web import (
    Application,
    HTTPForbidden,
    HTTPUnauthorized,
    Request,
    Response,
    get,
    post,
)
from aiohttp_session import get_session, new_session
from aiohttp_session import setup as setup_session
from aiohttp_session.redis_storage import RedisStorage
from redis.asyncio import Redis

from ...concept import Case, Identity
from ...helper.aiohttp import client_ip, json_response
from ...helper.logging import get_logger
from ...helper.redis import create_redis_lock
from ...helper.tracing import trace_user_op
from ..storage import get_fusion_storage
from .backend import FusionAuthBackend, instanciate_auth
from .config import FusionAuthAPIConfig

_LOGGER = get_logger('server.auth.impl')
_USERNAME_FIELD = 'username'
_FUSION_AUTH_API = 'fusion_auth_api'
FUSION_API_TOKEN_HEADER = 'X-Fusion-API-Token'


def _unauthorized(request: Request, operation: str, context: dict):
    trace_user_op(
        Identity(username=client_ip(request)),
        operation,
        granted=False,
        context=context,
        exception=HTTPUnauthorized,
    )


def can_access_case(identity: Identity, case: Case) -> bool:
    """Determine if identity can access case"""
    if not case.acs:
        return True
    return bool(case.acs.intersection(identity.acs))


@dataclass(kw_only=True)
class FusionAuthAPI:
    """Fusion Auth API"""

    redis: Redis
    config: FusionAuthAPIConfig
    authorize_impl: (
        Callable[[Identity, Request, dict], Awaitable[bool]] | None
    ) = None

    @cached_property
    def backend(self) -> FusionAuthBackend | None:
        """Authentication backend"""
        return instanciate_auth(self.config.backend)

    def _check_backend_availability(self, request: Request):
        if self.backend is None:
            _LOGGER.warning("authentication backend is not available")
            _unauthorized(request, 'retrieve_config', {})

    def setup(self, webapp: Application):
        """Setup web application routes"""
        _LOGGER.info("install auth api...")
        webapp[_FUSION_AUTH_API] = self
        webapp.add_routes(
            [
                get('/api/auth/is_logged', self.is_logged),
                post('/api/auth/login', self.login),
                get('/api/auth/logout', self.logout),
                get('/api/auth/config', self.retrieve_config),
                get('/api/auth/identities', self.retrieve_identities),
            ]
        )
        storage = RedisStorage(
            self.redis,
            cookie_name=self.config.cookie.name,
            domain=self.config.cookie.domain,
            max_age=self.config.cookie.max_age,
            path=self.config.cookie.path,
            secure=self.config.cookie.secure,
            httponly=self.config.cookie.httponly,
            samesite=self.config.cookie.samesite,
        )
        setup_session(webapp, storage)
        _LOGGER.info("auth api installed.")

    def can_access_case(self, identity: Identity, case: Case) -> bool:
        """Determine if identity can access case"""
        return can_access_case(identity, case)

    async def authorize(
        self,
        request: Request,
        operation: str,
        *,
        context: dict | None = None,
    ) -> Identity:
        """Authorize request or raise an exception"""
        context = context or {}
        # grant access to api client or not
        key = request.headers.get(FUSION_API_TOKEN_HEADER)
        username = self.config.key_name_mapping.get(key)
        if username:
            identity = Identity(username=username)
            trace_user_op(identity, operation, granted=True, context=context)
            return identity
        # if authentication backend is not available
        if self.backend is None:
            _LOGGER.warning("authentication backend is not available")
            _unauthorized(request, operation, context)
        # if authorization impl is not available
        if self.authorize_impl is None:
            _LOGGER.warning("authorization callback is not available")
            _unauthorized(request, operation, context)
        # grant access to authenticated user or not
        _LOGGER.debug("request headers: %s", request.headers)
        session = await get_session(request)
        username = session.get(_USERNAME_FIELD)
        if not username:
            _LOGGER.debug("username not found in session")
            _unauthorized(request, operation, context)
        identity = await self.backend.is_logged(username)
        if not identity:
            _LOGGER.debug("identity not found for username: %s", username)
            _unauthorized(request, operation, context)
        try:
            granted = await self.authorize_impl(identity, request, context)
        except:
            _LOGGER.exception("authorize_impl exception!")
            granted = False
        exception = None if granted else HTTPForbidden
        trace_user_op(
            identity,
            operation,
            granted=granted,
            context=context,
            exception=exception,
        )
        return identity

    async def is_logged(self, request: Request) -> Response:
        """Determine if user is authenticated"""
        identity = await self.authorize(request, 'is_logged')
        return json_response(data=identity.to_dict())

    async def login(self, request: Request) -> Response:
        """Authenticate user"""
        self._check_backend_availability(request)
        session = await new_session(request)
        ip_identity = Identity(username=client_ip(request))
        try:
            body = await request.json()
        except JSONDecodeError:
            trace_user_op(ip_identity, 'login', granted=False)
            return json_response(status=400, message="Bad request")
        data = body.get('data')
        if not data:
            trace_user_op(ip_identity, 'login', granted=False)
            return json_response(status=400, message="Bad request")
        identity = await self.backend.login(data)
        if not identity:
            trace_user_op(ip_identity, 'login', granted=False)
            return json_response(status=400, message="Login failed")
        storage = get_fusion_storage(request)
        lock = create_redis_lock(self.redis, 'identity-cache-lock')
        async with lock:
            await storage.store_identity(identity)
        session[_USERNAME_FIELD] = identity.username
        trace_user_op(ip_identity, 'login', granted=True)
        return json_response(data=identity.to_dict())

    async def logout(self, request: Request) -> Response:
        """Deauthenticate user"""
        self._check_backend_availability(request)
        identity = await self.authorize(request, 'logout')
        await self.backend.logout(identity)
        session = await get_session(request)
        session.invalidate()
        return json_response()

    async def retrieve_config(self, request: Request) -> Response:
        """Retrieve authentication backend configuration"""
        # if authentication backend is not available
        self._check_backend_availability(request)
        info = await self.backend.info()
        return json_response(data=info.to_dict())

    async def retrieve_identities(self, request: Request) -> Response:
        """Retrieve stored identities"""
        identity = await self.authorize(request, 'retrieve_identities')
        storage = get_fusion_storage(request)
        identities = [
            identity.to_dict()
            async for identity in storage.enumerate_identities()
        ]
        return json_response(data=identities)


def get_fusion_auth_api(request: Request) -> FusionAuthAPI:
    """Retrieve FusionAuthAPI instance from request"""
    return request.app[_FUSION_AUTH_API]
