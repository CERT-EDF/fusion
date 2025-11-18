"""Fusion Notifier"""

from dataclasses import dataclass, field
from ssl import SSLContext

from aiohttp import (
    ClientConnectionError,
    ClientSession,
    ClientTimeout,
    Fingerprint,
)

from ..concept import Event
from .logging import get_logger
from .pubsub import case_pubsub_channel
from .redis import Redis
from .serializing import dump_json

_LOGGER = get_logger('helper.notifier')
_FUSION_NOTIFIER_HEADER = 'X-Fusion-Notifier-Token'


def create_notifier_session(api_key: str, timeout: float) -> ClientSession:
    """Create aiohttp.ClientSession instance for FusionNotifier"""
    return ClientSession(
        headers={_FUSION_NOTIFIER_HEADER: api_key},
        timeout=ClientTimeout(total=timeout),
        raise_for_status=False,
    )


@dataclass(kw_only=True)
class FusionNotifier:
    """Fusion Notifier"""

    redis: Redis
    session: ClientSession
    api_ssl: Fingerprint | SSLContext | bool = True
    webhooks: list[str] = field(default_factory=list)

    async def _redis_notify(self, event_dct: dict, channel: str):
        message = dump_json(event_dct)
        await self.redis.publish(channel, message)

    async def _webhook_notify(self, event_dct: dict, webhook: str):
        try:
            async with self.session.post(
                webhook,
                ssl=self.api_ssl,
                json=event_dct,
            ) as resp:
                _LOGGER.info("notify %s (status=%d)", webhook, resp.status)
        except TimeoutError:
            _LOGGER.error("notify %s (timeout)", webhook)
        except ClientConnectionError:
            _LOGGER.exception("notify %s (connection)", webhook)

    async def notify(self, event: Event):
        """Send event to endpoints (including global endpoint if set)"""
        event_dct = event.to_dict()
        # send to redis pubsub channel
        channel = case_pubsub_channel(event.case)
        await self._redis_notify(event_dct, channel)
        # send to webhooks
        webhooks = []
        webhooks.extend(self.webhooks)
        webhooks.extend(event.case.webhooks)
        for webhook in webhooks:
            await self._webhook_notify(event_dct, webhook)
