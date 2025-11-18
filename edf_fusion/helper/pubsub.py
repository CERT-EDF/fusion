"""Fusion Core Pub/Sub Helper"""

from asyncio import Event
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from functools import partial

from redis.asyncio import Redis

from ..concept import Case, Concept, ConceptType
from .serializing import dump_json, load_json

__TERMINATE__ = '__TERMINATE__'


def case_pubsub_channel(case: Case) -> str:
    """Generate pubsub channel name from case metadata"""
    return f'fusion-pubsub-case-{case.guid}'


@dataclass(kw_only=True)
class PubSub:
    """Publisher Subscriber System"""

    redis: Redis
    default_channel: str = 'fusion-pubsub-general'
    _terminating: Event = field(default_factory=Event)
    _subscribers: dict[str, set[str]] = field(
        default_factory=partial(defaultdict, set)
    )

    async def publish(self, concept: Concept, channel: str | None = None):
        """Publish"""
        channel = channel or self.default_channel
        message = dump_json(concept.to_dict())
        await self.redis.publish(channel, message)

    async def subscribe(
        self,
        client_guid: str,
        channel: str | None = None,
        concept_cls: ConceptType | None = None,
    ) -> AsyncIterator[str | Concept]:
        """Subscribe"""
        channel = channel or self.default_channel
        if self._terminating.is_set():
            return
        # register subscriber
        self._subscribers[channel].add(client_guid)
        # loop until unsubscribe is called
        async with self.redis.pubsub() as pubsub:
            await pubsub.subscribe(channel)
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=None
                )
                if message is None:
                    continue
                data = message['data'].decode()
                if data == __TERMINATE__:
                    break
                if not concept_cls:
                    yield data
                    continue
                yield concept_cls.from_dict(load_json(data))

    def unsubscribe(self, client_guid: str, channel: str | None = None):
        """Unsubscribe"""
        channel = channel or self.default_channel
        self._subscribers[channel].discard(client_guid)

    def subscribers(self, channel: str | None = None) -> set[str]:
        """Retrieve channel subscribers"""
        channel = channel or self.default_channel
        return self._subscribers[channel]

    async def terminate(self):
        """Terminate all subscriptions"""
        self._terminating.set()
        for channel in self._subscribers.keys():
            await self.redis.publish(channel, __TERMINATE__)
