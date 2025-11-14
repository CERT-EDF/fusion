"""Fusion Auth API Config"""

from dataclasses import dataclass
from enum import Enum
from functools import cached_property
from os import urandom
from typing import Self

from ...helper.config import ConfigError
from ...helper.logging import get_logger
from ...helper.serializing import Loadable

IRON_SERVER_USERNAME = 'iron_server'

_LOGGER = get_logger('server.auth.config')


class AuthStrategy(Enum):
    """Authentication Strategy"""

    BASIC = 'basic'
    KEYCLOAK = 'keycloak'


@dataclass(kw_only=True)
class User(Loadable):
    """Basic user"""

    username: str
    digest: str
    groups: set[str]

    @classmethod
    def from_dict(cls, dct: dict) -> Self:
        return cls(
            username=dct['username'],
            digest=dct['digest'],
            groups=set(dct.get('groups', [])),
        )


@dataclass(kw_only=True)
class BasicConfig(Loadable):
    """Basic config"""

    users: dict[str, User]
    groups: set[str]

    @classmethod
    def from_dict(cls, dct: dict) -> Self:
        users = [User.from_dict(item) for item in dct.get('users', [])]
        return cls(
            users={item.username: item for item in users},
            groups=set(dct.get('groups', [])),
        )


@dataclass(kw_only=True)
class KeycloakConfig(Loadable):
    """Keycloak config"""

    url: str | None
    client_id: str | None
    realm_name: str | None
    client_secret: str | None
    redirect_uri: str | None
    include_auth: bool
    verify: bool

    @cached_property
    def server_url(self) -> str:
        """Server url"""
        return f"{self.url}/auth/" if self.include_auth else f"{self.url}/"

    @classmethod
    def from_dict(cls, dct: dict) -> Self:
        verify = dct.get('verify', True)
        if not verify:
            _LOGGER.warning("client-side certificate validation disabled!")
        return cls(
            url=dct.get('url'),
            client_id=dct.get('client_id'),
            realm_name=dct.get('realm_name'),
            client_secret=dct.get('client_secret'),
            redirect_uri=dct.get('redirect_uri'),
            include_auth=dct.get('include_auth', True),
            verify=verify,
        )


@dataclass
class AuthBackendConfig(Loadable):
    """Auth Backend config"""

    strategy: AuthStrategy
    basic: BasicConfig
    keycloak: KeycloakConfig

    @cached_property
    def enabled(self) -> bool:
        """Determine if auth backend is enabled based on strategy value"""
        return bool(self.strategy)

    @classmethod
    def from_dict(cls, dct: dict) -> Self:
        return cls(
            strategy=AuthStrategy(dct.get('strategy', 'basic')),
            basic=BasicConfig.from_dict(dct.get('basic', {})),
            keycloak=KeycloakConfig.from_dict(dct.get('keycloak', {})),
        )


@dataclass(kw_only=True)
class Client(Loadable):
    """Client"""

    name: str
    key: str

    @classmethod
    def from_dict(cls, dct: dict):
        return cls(name=dct['name'], key=dct['key'])


@dataclass(kw_only=True)
class CookieConfig(Loadable):
    """Cookie config"""

    secret_key: str | bytes
    domain: str | None
    max_age: int | None
    path: str
    secure: bool | None
    httponly: bool
    samesite: str | None
    name: str

    @classmethod
    def from_dict(cls, dct: dict):
        return cls(
            secret_key=dct.get('secret_key', urandom(32)),
            domain=dct.get('domain'),
            max_age=dct.get('max_age'),
            path=dct.get('path', '/'),
            secure=dct.get('secure'),
            httponly=dct.get('httponly', True),
            samesite=dct.get('samesite'),
            name=dct.get('name', 'FUSION_SESSION'),
        )


@dataclass(kw_only=True)
class FusionAuthAPIConfig(Loadable):
    """Fusion Auth API Configuration"""

    cookie: CookieConfig
    backend: AuthBackendConfig
    clients: list[Client]
    iron_key: str | None
    can_delete_acs: set[str]

    @cached_property
    def key_name_mapping(self) -> dict[str, str]:
        """Client key/name mapping"""
        self._validate()
        key_name_mapping = {client.key: client.name for client in self.clients}
        if self.iron_key:
            key_name_mapping[self.iron_key] = IRON_SERVER_USERNAME
        return key_name_mapping

    def _validate(self) -> bool:
        keys = set()
        names = set()
        for client in self.clients:
            keys.add(client.key)
            names.add(client.name)
        if len(keys) != len(self.clients):
            raise ConfigError("client key collision")
        if len(names) != len(self.clients):
            raise ConfigError("client name collision")
        if IRON_SERVER_USERNAME in names:
            raise ConfigError("iron server name collision")
        if self.iron_key and self.iron_key in keys:
            raise ConfigError("iron server key collision")

    @classmethod
    def from_dict(cls, dct: dict) -> Self:
        return cls(
            cookie=CookieConfig.from_dict(dct.get('cookie', {})),
            backend=AuthBackendConfig.from_dict(dct['backend']),
            clients=[Client.from_dict(item) for item in dct['clients']],
            iron_key=dct['iron_key'],
            can_delete_acs=set(dct.get('can_delete_acs', [])),
        )
