"""Redis helper"""

from aiohttp.web import Application, Request
from redis.asyncio import Redis
from redis.asyncio.lock import Lock

from .logging import get_logger

_LOGGER = get_logger('helper.redis')
_FUSION_REDIS = 'fusion_redis'


def create_redis(url: str) -> Redis:
    """Create redis instance from url"""
    _LOGGER.info("creating redis instance...")
    return Redis.from_url(url)


async def close_redis(redis: Redis):
    """Terminate redis instance gracefully"""
    _LOGGER.info("closing redis instance...")
    await redis.aclose()


async def _cleanup_redis(webapp: Application):
    await close_redis(webapp[_FUSION_REDIS])


def setup_redis(webapp: Application, url: str) -> Redis:
    """Create redis instance from url and save it in webapp"""
    redis = create_redis(url)
    webapp[_FUSION_REDIS] = redis
    webapp.on_cleanup.append(_cleanup_redis)
    return redis


def get_redis(app_or_req: Application | Request) -> Redis:
    """Retrieve Redis instance from request"""
    if isinstance(app_or_req, Request):
        app_or_req = app_or_req.app
    return app_or_req[_FUSION_REDIS]


def create_redis_lock(redis: Redis, name: str, **kwargs) -> Lock:
    """Create redis based lock"""
    return Lock(redis, name, **kwargs)
