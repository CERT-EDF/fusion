"""Fusion Core aiohttp Helper"""

from collections.abc import AsyncIterator
from json import JSONDecodeError
from uuid import UUID

from aiohttp import (
    BodyPartReader,
    ClientResponse,
    ClientSession,
    ClientTimeout,
)
from aiohttp.web import Request, Response, StreamResponse
from aiohttp.web import json_response as _json_response
from aiohttp_sse import sse_response

from ..concept import Concept, ConceptType
from .logging import get_logger
from .pubsub import PubSub
from .serializing import load_json
from .streaming import DEFAULT_CHUNK_SIZE

Data = dict | list | str | None


_LOGGER = get_logger('helper.aiohttp')


def get_guid(request: Request, element: str) -> UUID | None:
    """Get UUID from request match info"""
    try:
        return UUID(request.match_info[element])
    except ValueError:
        return None


async def get_json_body(request: Request) -> dict | list | None:
    """Load object from JSON request body"""
    try:
        return await request.json()
    except JSONDecodeError:
        _LOGGER.exception("bad request")
        return None


def json_response(
    *, data: Data = None, status: int = 200, message: str = None
) -> Response:
    """Build JSON response with a combination of data, status and message"""
    body = {'status': status}
    if status >= 400:
        body.update({'message': message})
        _LOGGER.warning("status=%s message='%s'", status, message)
    if data is not None:
        body.update({'data': data, 'count': len(data)})
    return _json_response(body, status=status)


def client_ip(request: Request) -> str:
    """Get client ip for request"""
    ipaddr = request.headers.get('X-Forwarded-For')
    if request.forwarded:
        ipaddr = request.forwarded[0]['for']
    if not ipaddr:
        ipaddr = request.remote
    return ipaddr


async def stream_response(
    request: Request, filename: str, content: AsyncIterator[bytes]
) -> StreamResponse:
    """Feed stream response with given content"""
    filename = filename.replace('"', '')
    response = StreamResponse(
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )
    response.enable_chunked_encoding()
    await response.prepare(request)
    async for chunk in content:
        await response.write(chunk)
    return response


async def stream_client_response(
    response: ClientResponse,
    chunk_size: int = 64 * 1024,
) -> AsyncIterator[bytes]:
    """Iterate over chunks of client response body"""
    while True:
        chunk = await response.content.read(chunk_size)
        if not chunk:
            break
        yield chunk


async def stream_multipart_parts(
    request: Request, names: set[str]
) -> AsyncIterator[BodyPartReader]:
    """Extract interesting parts from multipart and release others"""
    multipart = await request.multipart()
    async for part in multipart:
        if part.name in names:
            yield part
        await part.release()


async def stream_multipart_part_content(
    part: BodyPartReader, chunk_size: int = DEFAULT_CHUNK_SIZE
) -> AsyncIterator[bytes]:
    """Iterate over chunks of multipart part body"""
    while True:
        chunk = await part.read_chunk(chunk_size)
        if not chunk:
            break
        yield bytes(chunk)


async def pubsub_sse_response(
    request: Request,
    pubsub: PubSub,
    client_guid: str,
    channel: str | None = None,
) -> StreamResponse:
    """Pubsub-based SSE response"""
    async with sse_response(request) as response:
        try:
            while response.is_connected():
                async for data in pubsub.subscribe(client_guid, channel):
                    await response.send(data)
        finally:
            pubsub.unsubscribe(client_guid)
        return response


async def sse_client(
    session: ClientSession, endpoint: str, concept_cls: ConceptType, **kwargs
) -> AsyncIterator[Concept]:
    """SSE client"""
    if 'timeout' not in kwargs:
        kwargs['timeout'] = ClientTimeout()
    async with session.get(endpoint, **kwargs) as response:
        if response.status != 200:
            return
        async for line in response.content:
            line = line.strip().decode('utf-8')
            if not line.startswith('data: '):
                continue
            dct = load_json(line[6:])
            concept = concept_cls.from_dict(dct)
            yield concept
