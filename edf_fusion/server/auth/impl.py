"""Fusion Auth API Implementation"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
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
from ..storage import get_fusion_storage
from .backend import FusionAuthBackend, instanciate_auth
from .config import IRON_KEY_USERNAME, FusionAuthAPIConfig

_LOGGER = get_logger('server.auth.impl')
_USERNAME_FIELD = 'username'
_FUSION_AUTH_API = 'fusion_auth_api'
FUSION_API_TOKEN_HEADER = 'X-Fusion-API-Token'


class Access(Enum):
    """Access"""

    READ = 'read'
    CHANGE = 'change'


@dataclass(kw_only=True)
class Action:
    """Action"""

    name: str
    change: bool = False
    delete: bool = False
    context: dict = field(default_factory=dict)


def _trace_outcome(
    action: Action,
    identity: Identity,
    *,
    granted: bool,
    exception: Exception | None = None,
):
    """Trace user operation and raise exception if needed"""
    outcome = 'granted' if granted else 'refused'
    log_fun = _LOGGER.info if granted else _LOGGER.warning
    log_fun = _LOGGER.error if exception else log_fun
    log_fun("(audit) %s %s %s", outcome, identity.username, action)
    if exception:
        raise exception


@dataclass(kw_only=True)
class FusionAuthAPI:
    """Fusion Auth API"""

    redis: Redis
    config: FusionAuthAPIConfig
    authorize_impl: Callable[[Request, Action, Identity], Awaitable[bool]]

    @cached_property
    def backend(self) -> FusionAuthBackend | None:
        """Authentication backend"""
        return instanciate_auth(self.config.backend)

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

    def can_access_case(self, identity: Identity, case: Case) -> Access | None:
        """Determine if identity can access case"""
        if not case.acs:
            return Access.CHANGE
        if case.acs_ro.intersection(identity.acs):
            return Access.READ
        if case.acs.intersection(identity.acs):
            return Access.CHANGE
        return None

    def can_delete(self, identity: Identity) -> bool:
        """Determine if identity can delete"""
        return bool(self.config.can_delete_acs.intersection(identity.acs))

    def _is_backend_available(self):
        if self.backend is None:
            _LOGGER.warning("authentication backend is not available")
            return False
        return True

    async def _get_web_client_identity(
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

    def _get_api_client_identity(self, request: Request) -> Identity | None:
        key = request.headers.get(FUSION_API_TOKEN_HEADER)
        return self.config.key_identity_dct.get(key)

    async def _authorize_generic_client(
        self, request: Request, action: Action, identity: Identity
    ) -> bool:
        # prevent delete operation if applicable
        if action.delete and not self.can_delete(identity):
            _trace_outcome(
                action, identity, granted=False, exception=HTTPForbidden
            )
        # call service specific authorize_impl callback
        try:
            return await self.authorize_impl(request, action, identity)
        except:
            _LOGGER.exception("authorize_impl exception!")
            return False

    async def _authorize_api_client(
        self, request: Request, action: Action, identity: Identity
    ) -> bool:
        # iron key shortcut
        if identity.username == IRON_KEY_USERNAME:
            return True
        # perform generic checks
        return await self._authorize_generic_client(request, action, identity)

    async def authorize(self, request: Request, action: Action) -> Identity:
        """Authorize request or raise an exception"""
        storage = get_fusion_storage(request)
        ip_identity = Identity(username=client_ip(request))
        # process robot identity (if any)
        identity = self._get_api_client_identity(request)
        if identity:
            granted = await self._authorize_api_client(
                request, action, identity
            )
            exception = None if granted else HTTPForbidden
            _trace_outcome(
                action, identity, granted=granted, exception=exception
            )
            await storage.store_identity(identity)
            return identity
        # determine if web client authentication is available
        if not self._is_backend_available():
            _trace_outcome(
                action, ip_identity, granted=False, exception=HTTPForbidden
            )
        # process web client identity (if any)
        identity = await self._get_web_client_identity(request)
        if identity:
            granted = await self._authorize_generic_client(
                request, action, identity
            )
            exception = None if granted else HTTPForbidden
            _trace_outcome(
                action, identity, granted=granted, exception=exception
            )
            await storage.store_identity(identity)
            return identity
        # identity is missing
        _trace_outcome(
            action, ip_identity, granted=False, exception=HTTPUnauthorized
        )

    async def is_logged(self, request: Request) -> Response:
        """Determine if user is authenticated"""
        action = Action(name='is_logged')
        identity = await self.authorize(request, action)
        return json_response(data=identity.to_dict())

    async def login(self, request: Request) -> Response:
        """Authenticate user"""
        action = Action(name='login')
        ip_identity = Identity(username=client_ip(request))
        if not self._is_backend_available():
            _trace_outcome(action, ip_identity, granted=False)
            return json_response(status=501, message="Backend not available")
        session = await new_session(request)
        try:
            body = await request.json()
        except JSONDecodeError:
            _trace_outcome(action, ip_identity, granted=False)
            return json_response(status=400, message="Bad request")
        data = body.get('data')
        if not data:
            _trace_outcome(action, ip_identity, granted=False)
            return json_response(status=400, message="Bad request")
        identity = await self.backend.login(data)
        if not identity:
            _trace_outcome(action, ip_identity, granted=False)
            return json_response(status=400, message="Login failed")
        session[_USERNAME_FIELD] = identity.username
        _trace_outcome(action, ip_identity, granted=True)
        return json_response(data=identity.to_dict())

    async def logout(self, request: Request) -> Response:
        """Deauthenticate user"""
        action = Action(name='logout')
        ip_identity = Identity(username=client_ip(request))
        if not self._is_backend_available():
            _trace_outcome(action, ip_identity, granted=False)
            return json_response(status=501, message="Backend not available")
        identity = await self.authorize(request, action)
        await self.backend.logout(identity)
        session = await get_session(request)
        session.invalidate()
        return json_response()

    async def retrieve_config(self, request: Request) -> Response:
        """Retrieve authentication backend configuration"""
        action = Action(name='retrieve_config')
        ip_identity = Identity(username=client_ip(request))
        if not self._is_backend_available():
            _trace_outcome(action, ip_identity, granted=False)
            return json_response(status=501, message="Backend not available")
        info = await self.backend.info()
        return json_response(data=info.to_dict())

    async def retrieve_identities(self, request: Request) -> Response:
        """Retrieve stored identities"""
        action = Action(name='retrieve_identities')
        identity = await self.authorize(request, action)
        storage = get_fusion_storage(request)
        identities = [
            identity.to_dict()
            async for identity in storage.enumerate_identities()
        ]
        return json_response(data=identities)


def get_fusion_auth_api(request: Request) -> FusionAuthAPI:
    """Retrieve FusionAuthAPI instance from request"""
    return request.app[_FUSION_AUTH_API]
