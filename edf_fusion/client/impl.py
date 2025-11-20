"""Fusion client"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from aiohttp import ClientResponse, ClientSession, CookieJar

from ..concept import Concept, ConceptType
from ..helper.aiohttp import sse_client, stream_client_response
from ..helper.logging import get_logger
from ..helper.streaming import stream_to_file
from .config import FusionClientConfig

_LOGGER = get_logger('client.impl')
_APPLICATION_JSON = 'application/json'


@dataclass(kw_only=True)
class FusionClient:
    """Fusion client"""

    config: FusionClientConfig
    session: ClientSession

    def _request_kwargs(self, **kwargs):
        req_kwargs = {
            'ssl': self.config.api_ssl,
            'proxy': self.config.proxy_url,
            'proxy_auth': self.config.proxy_auth,
            'proxy_headers': self.config.proxy_headers,
            'timeout': self.config.timeout,
        }
        req_kwargs.update(kwargs)
        return req_kwargs

    async def _handle_json_resp(
        self,
        response: ClientResponse,
        concept_cls: ConceptType | None = None,
    ) -> list[Concept] | Concept | None:
        _LOGGER.debug("response headers: %s", response.headers)
        if response.content_type != _APPLICATION_JSON:
            _LOGGER.error("request failed with status=%d", response.status)
            return None
        body = await response.json()
        if response.status >= 400:
            func = _LOGGER.warning if response.status < 500 else _LOGGER.error
            func("request failed with status=%d", response.status)
            func("server message: %s", body.get('message'))
            return None
        if not concept_cls:
            return None  # caller does not expect a result
        data = body.get('data')
        if isinstance(data, list):
            return [concept_cls.from_dict(dct) for dct in data]
        if isinstance(data, dict):
            return concept_cls.from_dict(data)
        return None

    async def get(
        self, endpoint: str, concept_cls: ConceptType | None = None, **kwargs
    ) -> list[Concept] | Concept | None:
        """Send GET request to the server"""
        kwargs = self._request_kwargs(**kwargs)
        async with self.session.get(endpoint, **kwargs) as response:
            return await self._handle_json_resp(response, concept_cls)

    async def put(
        self,
        endpoint: str,
        concept: Concept | None = None,
        concept_cls: ConceptType | None = None,
        **kwargs,
    ) -> list[Concept] | Concept | None:
        """Send PUT request to the server"""
        kwargs = self._request_kwargs(**kwargs)
        if concept:
            kwargs['json'] = concept.to_dict()
        async with self.session.put(endpoint, **kwargs) as response:
            return await self._handle_json_resp(response, concept_cls)

    async def post(
        self,
        endpoint: str,
        concept: Concept | None = None,
        concept_cls: ConceptType | None = None,
        **kwargs,
    ) -> list[Concept] | Concept | None:
        """Send POST request to the server"""
        kwargs = self._request_kwargs(**kwargs)
        if concept:
            kwargs['json'] = concept.to_dict()
        async with self.session.post(endpoint, **kwargs) as response:
            return await self._handle_json_resp(response, concept_cls)

    async def delete(self, endpoint: str, **kwargs) -> bool:
        """Send DELETE request to the server"""
        kwargs = self._request_kwargs(**kwargs)
        async with self.session.delete(endpoint, **kwargs) as response:
            await self._handle_json_resp(response)
            return response.status == 200

    async def sse(
        self, endpoint: str, concept_cls: ConceptType, **kwargs
    ) -> AsyncIterator[Concept]:
        """SSE"""
        kwargs = self._request_kwargs(**kwargs)
        async for concept in sse_client(
            self.session, endpoint, concept_cls, **kwargs
        ):
            yield concept

    async def download(
        self, endpoint: str, output: Path, **kwargs
    ) -> Path | None:
        """Download attachment from server"""
        kwargs = self._request_kwargs(**kwargs)
        async with self.session.get(endpoint, **kwargs) as response:
            if response.status != 200:
                return None
            if output.is_dir():
                content_disposition = response.content_disposition
                if not content_disposition:
                    return None
                if not content_disposition.filename:
                    return None
                output = output / content_disposition.filename
            await stream_to_file(output, stream_client_response(response))
        return output


def create_session(
    config: FusionClientConfig, unsafe: bool = False
) -> ClientSession:
    """Create a client session for fusion client"""
    return ClientSession(
        base_url=config.api_url,
        headers=config.headers,
        trust_env=config.proxy_trust_env,
        cookie_jar=CookieJar(unsafe=unsafe),
        raise_for_status=False,
    )
