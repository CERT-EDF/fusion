"""Configuration"""

from dataclasses import dataclass
from pathlib import Path
from typing import Self, Type

from ..helper.config import ConfigError
from ..helper.serializing import Loadable


@dataclass(kw_only=True)
class FusionServerConfig(Loadable):
    """Fusion Server Config"""

    host: str
    port: int
    redis_url: str
    client_max_size: int

    @classmethod
    def from_dict(cls, dct: dict) -> Self:
        return cls(
            host=dct['host'],
            port=dct['port'],
            redis_url=dct['redis_url'],
            client_max_size=dct['client_max_size'],
        )


@dataclass(kw_only=True)
class FusionStorageConfig(Loadable):
    """Fusion Storage Config"""

    directory: Path

    @classmethod
    def from_dict(cls, dct: dict) -> Self:
        return cls(directory=Path(dct['directory']))


@dataclass(kw_only=True)
class FusionSynchronizerConfig(Loadable):
    """Fusion Synchronizer Config"""

    enabled: bool
    directory: Path | None

    @classmethod
    def from_dict(cls, dct: dict):
        directory = dct.get('directory')
        return cls(
            enabled=dct.get('enabled', False),
            directory=Path(directory) if directory else None,
        )


@dataclass(kw_only=True)
class FusionAnalyzerConfig(Loadable):
    """Fusion Analyzer Config"""

    enabled: bool
    workers: int

    @classmethod
    def from_dict(cls, dct):
        return cls(
            enabled=dct.get('enabled', False),
            workers=max(1, dct.get('workers', 1)),
        )


FusionAnalyzerConfigType = Type[FusionAnalyzerConfig]


@dataclass(kw_only=True)
class FusionAnalyzerMapping(Loadable):
    """Fusion Analyzer Mapping"""

    _mapping: dict[str, dict]

    @classmethod
    def from_dict(cls, dct: dict[str, dict]):
        return cls(_mapping=dct)

    def get(
        self, name: str, config_cls: FusionAnalyzerConfigType
    ) -> FusionAnalyzerConfig:
        """Retrieve analyzer configuration by name"""
        dct = self._mapping.get(name)
        if not dct:
            raise ConfigError(f"missing config for {name} analyzer")
        return config_cls.from_dict(dct)
