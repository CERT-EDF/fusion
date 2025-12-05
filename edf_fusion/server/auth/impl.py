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


def _deny(
    request: Request,
    operation: str,
    context: dict,
    identity: Identity | None = None,
):
    is_authenticated = bool(identity)
    if not identity:
        identity = Identity(username=client_ip(request))
    trace_user_op(
        identity,
        operation,
        granted=False,
        context=context,
        exception=HTTPForbidden if is_authenticated else HTTPUnauthorized,
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

    def _check_backend_availability(self):
        if self.backend is None:
            _LOGGER.warning("authentication backend is not available")
            return False
        return True

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

    def _is_api_access_granted(self, request: Request) -> Identity | None:
        key = request.headers.get(FUSION_API_TOKEN_HEADER)
        username = self.config.key_name_mapping.get(key)
        if username:
            return Identity(username=username)
        return None

    def _is_user_authorization_implemented(self) -> bool:
        # if authentication backend is not available
        if not self._check_backend_availability():
            return False
        # if authorization impl is not available
        if self.authorize_impl is None:
            _LOGGER.warning("authorization callback is not available")
            return False
        return True

    async def _get_identity_from_request(
        self, request: Request
    ) -> Identity | None:
        _LOGGER.debug("request headers: %s", request.headers)
        session = await get_session(request)
        username = session.get(_USERNAME_FIELD)
        if not username:
            _LOGGER.debug("username not found in session")
            return None
        identity = await self.backend.is_logged(username)
        if not identity:
            _LOGGER.debug("identity not found for username: %s", username)
            return None
        return identity

    async def authorize(
        self,
        request: Request,
        operation: str,
        *,
        context: dict | None = None,
    ) -> Identity:
        """Authorize request or raise an exception"""
        context = context or {}
        # grant access to api client or not (all operations are authorized)
        identity = self._is_api_access_granted(request)
        if identity:
            trace_user_op(identity, operation, granted=True, context=context)
            return identity
        # determine if user access is implemented (backend and callback)
        if not self._is_user_authorization_implemented():
            _deny(request, operation, context)
        # grant access to authenticated user or not
        identity = await self._get_identity_from_request(request)
        if not identity:
            _deny(request, operation, context)
        # prevent delete operation from users without privileges
        is_delete_op = context.get('is_delete_op', False)
        if is_delete_op and not self.config.can_delete_acs.intersection(
            identity.acs
        ):
            _deny(request, operation, context, identity)
        # call service specific authorization implementation
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
        ip_identity = Identity(username=client_ip(request))
        if not self._check_backend_availability():
            trace_user_op(ip_identity, 'login', granted=False)
            return json_response(status=501, message="Backend not available")
        session = await new_session(request)
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
        ip_identity = Identity(username=client_ip(request))
        if not self._check_backend_availability():
            trace_user_op(ip_identity, 'logout', granted=False)
            return json_response(status=501, message="Backend not available")
        identity = await self.authorize(request, 'logout')
        await self.backend.logout(identity)
        session = await get_session(request)
        session.invalidate()
        return json_response()

    async def retrieve_config(self, request: Request) -> Response:
        """Retrieve authentication backend configuration"""
        # if authentication backend is not available
        ip_identity = Identity(username=client_ip(request))
        if not self._check_backend_availability():
            trace_user_op(ip_identity, 'retrieve_config', granted=False)
            return json_response(status=501, message="Backend not available")
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
