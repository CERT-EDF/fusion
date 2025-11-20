"""Fusion Auth API Client"""

from dataclasses import dataclass

from ...concept import AuthInfo, Concept, Identity
from ...helper.logging import get_logger
from ..impl import FusionClient

_LOGGER = get_logger('client.api.auth')


@dataclass(kw_only=True)
class _Credentials(Concept):
    """Credentials"""

    username: str
    password: str

    @classmethod
    def from_dict(cls, dct):
        raise NotImplementedError("Credentials.from_dict shall not be called")

    def to_dict(self):
        return {'data': {'username': self.username, 'password': self.password}}

    def update(self, dct):
        raise NotImplementedError("Credentials.update shall not be called")


@dataclass(kw_only=True)
class FusionAuthAPIClient:
    """Fusion Auth API Client"""

    fusion_client: FusionClient

    async def is_logged(self) -> Identity | None:
        """Determine if user is authenticated"""
        _LOGGER.info("checking if still logged in")
        endpoint = '/api/auth/is_logged'
        return await self.fusion_client.get(endpoint, concept_cls=Identity)

    async def login(self, username: str, password: str) -> Identity | None:
        """Authenticate user"""
        _LOGGER.info("logging in as %s", username)
        creds = _Credentials(username=username, password=password)
        endpoint = '/api/auth/login'
        return await self.fusion_client.post(
            endpoint, creds, concept_cls=Identity
        )

    async def logout(self):
        """Deauthenticate user"""
        _LOGGER.info("logging out")
        endpoint = '/api/auth/logout'
        return await self.fusion_client.get(endpoint)

    async def config(self) -> AuthInfo | None:
        """Authentication configuration"""
        _LOGGER.info("retrieving authentication configuration")
        endpoint = '/api/auth/config'
        return await self.fusion_client.get(endpoint, concept_cls=AuthInfo)

    async def identities(self) -> list[Identity] | None:
        """Retrieve known identities"""
        _LOGGER.info("retrieving identities")
        endpoint = '/api/auth/identities'
        return await self.fusion_client.get(endpoint, concept_cls=Identity)
