"""Fusion Storage ABC"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from shutil import rmtree
from uuid import UUID

from aiohttp.web import Application, Request

from ..concept import Case, Identities, Identity
from ..helper.filesystem import disk_usage
from ..helper.logging import get_logger
from .config import FusionStorageConfig

_LOGGER = get_logger('server.storage')
_FUSION_STORAGE = 'fusion_storage'


@dataclass(kw_only=True)
class SyncStorage:
    """Sync Storage"""

    case: Case
    directory: Path

    @cached_property
    def root(self) -> Path:
        """Root directory"""
        return self.directory / f'[{self.case.tsid}] {self.case.name}'

    @cached_property
    def information(self) -> Path:
        """Information directory"""
        return self.root / '01 - Information'

    @cached_property
    def collectors(self) -> Path:
        """Information directory"""
        return self.root / '02 - Collectors'

    @cached_property
    def collections(self) -> Path:
        """Information directory"""
        return self.root / '03 - Collections'

    @cached_property
    def samples(self) -> Path:
        """Information directory"""
        return self.root / '04 - Samples'

    @cached_property
    def reports(self) -> Path:
        """Information directory"""
        return self.root / '05 - Reports'


@dataclass(kw_only=True)
class ConceptStorage:
    """Concept Storage"""

    directory: Path

    @property
    def size(self) -> int:
        """Concept disk usage"""
        return disk_usage(self.directory)

    @cached_property
    def data(self) -> Path:
        """Concept data file"""
        return self.directory / 'data'

    @cached_property
    def data_dir(self) -> Path:
        """Concept data directory"""
        return self.directory / 'data.d'

    @cached_property
    def metadata(self) -> Path:
        """Concept metadata file"""
        return self.directory / 'metadata.json'

    def create(self):
        """Create directory and parents, raise if directory exists"""
        self.directory.mkdir(parents=True, exist_ok=False)

    def remove(self):
        """Remove directory recursively"""
        if self.directory.is_dir():
            rmtree(self.directory)

    def remove_data_dir(self):
        """Remove data directory recursively"""
        if self.data_dir.is_dir():
            rmtree(self.data_dir)


@dataclass(kw_only=True)
class FusionStorage:
    """Storage ABC"""

    config: FusionStorageConfig

    @cached_property
    def cache_dir(self) -> Path:
        """Cache directory"""
        return self.config.directory / 'cache'

    @cached_property
    def identity_cache(self) -> Path:
        """Identity cache file"""
        return self.cache_dir / 'identities.json'

    async def startup(self):
        """Startup routine"""
        _LOGGER.info("nothing to startup.")

    async def cleanup(self):
        """Cleanup routine"""
        _LOGGER.info("nothing to cleanup.")

    async def context(self, _webapp: Application):
        """Context"""
        _LOGGER.info("storage starting up.")
        await self.startup()
        yield
        _LOGGER.info("storage cleaning up.")
        await self.cleanup()

    def setup(self, webapp: Application):
        """Setup web application storage"""
        _LOGGER.info("install storage...")
        webapp[_FUSION_STORAGE] = self
        webapp.cleanup_ctx.append(self.context)
        _LOGGER.info("storage installed.")

    async def attach_case(self, case_guid: UUID, next_case_guid: UUID) -> bool:
        """Attach case"""
        raise NotImplementedError

    async def create_case(self, managed: bool, dct) -> Case | None:
        """Create case"""
        raise NotImplementedError

    async def update_case(self, case_guid: UUID, dct) -> Case | None:
        """Update case"""
        raise NotImplementedError

    async def delete_case(self, case_guid: UUID) -> bool:
        """Delete case"""
        raise NotImplementedError

    async def retrieve_case(self, case_guid: UUID) -> Case | None:
        """Retrieve case"""
        raise NotImplementedError

    async def enumerate_cases(self) -> AsyncIterator[Case]:
        """Enumerate cases"""
        raise NotImplementedError

    async def store_identity(self, identity: Identity):
        """Store identity"""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        identities = Identities()
        if self.identity_cache.is_file():
            identities = Identities.from_filepath(self.identity_cache)
        identities.store(identity)
        identities.to_filepath(self.identity_cache)

    async def enumerate_identities(self) -> AsyncIterator[Identity]:
        """Enumerate identities"""
        if not self.identity_cache.is_file():
            return
        identities = Identities.from_filepath(self.identity_cache)
        for identity in identities.as_list:
            yield identity


def get_fusion_storage(app_or_req: Application | Request) -> FusionStorage:
    """Retrieve FusionStorage instance from request"""
    if isinstance(app_or_req, Request):
        app_or_req = app_or_req.app
    return app_or_req[_FUSION_STORAGE]
