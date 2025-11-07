"""Fusion Core Streaming Helper"""

from collections.abc import AsyncIterator, Iterator
from io import BufferedIOBase
from pathlib import Path

from aiofile import async_open

from .logging import get_logger

_LOGGER = get_logger('helper.streaming')
DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024


def stream_from_fobj(
    fobj: BufferedIOBase, chunk_size: int = DEFAULT_CHUNK_SIZE
) -> Iterator[bytes]:
    """Stream from file object"""
    while True:
        chunk = fobj.read(chunk_size)
        if not chunk:
            break
        yield chunk


async def stream_from_text(
    text: str, encoding: str = 'utf-8', chunk_size: int = DEFAULT_CHUNK_SIZE
) -> AsyncIterator[bytes]:
    """Stream encoded text"""
    data = text.encode(encoding=encoding)
    while data:
        yield data[:chunk_size]
        data = data[chunk_size:]


async def stream_from_file(
    filepath: Path, chunk_size: int = DEFAULT_CHUNK_SIZE
) -> AsyncIterator[bytes]:
    """Stream content from file asynchronously"""
    async with async_open(filepath, 'rb') as afobj:
        while True:
            chunk = await afobj.read(chunk_size)
            if not chunk:
                break
            yield chunk


async def stream_to_file(
    filepath: Path, content: AsyncIterator[bytes]
) -> int | None:
    """Stream content to file asynchronously"""
    total_size = 0
    try:
        async with async_open(filepath, 'wb') as afobj:
            async for chunk in content:
                chunk_size = await afobj.write(chunk)
                total_size += chunk_size
            await afobj.flush()
    except (OSError, RuntimeError):
        _LOGGER.exception("failed to write content to %s", filepath)
        return None
    return total_size
