"""Fusion Event API"""

from dataclasses import dataclass

from aiohttp.web import Application, HTTPBadRequest, Request, get
from redis.asyncio import Redis

from ...concept import Case, EventType
from ...helper.aiohttp import get_guid, pubsub_sse_response
from ...helper.logging import get_logger
from ...helper.notifier import FusionNotifier, create_notifier_session
from ...helper.pubsub import PubSub, case_pubsub_channel
from ..auth import get_fusion_auth_api
from ..storage import get_fusion_storage
from .config import FusionEventAPIConfig

_LOGGER = get_logger('server.event.impl')
_FUSION_EVENT_API = 'fusion_evt_api'


@dataclass(kw_only=True)
class FusionEventAPI:
    """Fusion Event API"""

    redis: Redis
    config: FusionEventAPIConfig
    event_cls: EventType
    _pubsub: PubSub | None = None
    _notifier: FusionNotifier | None = None

    def setup(self, webapp: Application):
        """Setup web application routes"""
        _LOGGER.info("install event api...")
        webapp[_FUSION_EVENT_API] = self
        webapp.add_routes(
            [
                get('/api/events/case/{case_guid}', self.subscribe),
            ]
        )
        webapp.cleanup_ctx.append(self.context)
        _LOGGER.info("event api installed.")

    async def context(self, webapp: Application):
        """Context"""
        if not self.config.enabled:
            _LOGGER.info("event api disabled.")
            yield
            return
        _LOGGER.info("startup event api...")
        session = create_notifier_session(
            self.config.api_key, self.config.timeout
        )
        async with session:
            self._pubsub = PubSub(redis=self.redis)
            self._notifier = FusionNotifier(
                redis=self.redis,
                session=session,
                api_ssl=self.config.api_ssl,
                webhooks=[self.config.webhook],
            )
            yield
            self._notifier = None
            await self._pubsub.terminate()
        _LOGGER.info("cleanup event api...")

    async def notify(self, category: str, case: Case, ext: dict | None = None):
        """Send event to endpoints (including global endpoint if set)"""
        if not self.config.enabled:
            return {}
        event = self.event_cls(category=category, case=case, ext=ext)
        await self._notifier.notify(event)

    async def subscribe(self, request: Request):
        """Subscribe to case event channel"""
        case_guid = get_guid(request, 'case_guid')
        fusion_storage = get_fusion_storage(request)
        fusion_auth_api = get_fusion_auth_api(request)
        if not case_guid:
            raise HTTPBadRequest(reason="Invalid case GUID")
        identity = await fusion_auth_api.authorize(
            request, 'subscribe', context={'case_guid': case_guid}
        )
        case = await fusion_storage.retrieve_case(case_guid)
        if not case_guid:
            raise HTTPBadRequest(reason="Failed to retrieve case from GUID")
        ext = {'username': identity.username}
        await self.notify(category='subscribe', case=case, ext=ext)
        channel = case_pubsub_channel(case)
        response = await pubsub_sse_response(
            request, self._pubsub, identity.username, channel
        )
        await self.notify(category='unsubscribe', case=case, ext=ext)
        return response


def get_fusion_evt_api(request: Request) -> FusionEventAPI:
    """Retrieve FusionEventAPI instance from request"""
    return request.app[_FUSION_EVENT_API]
