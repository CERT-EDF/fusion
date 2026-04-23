#!/usr/bin/env python3
"""Test Service"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from uuid import UUID

from aiohttp.web import Application, Request, run_app

from edf_fusion.concept import Case as FusionCase
from edf_fusion.concept import Event as FusionEvent
from edf_fusion.concept import Identity, Info
from edf_fusion.helper.logging import get_logger
from edf_fusion.helper.redis import setup_redis
from edf_fusion.server.auth import Action, FusionAuthAPI, FusionAuthAPIConfig
from edf_fusion.server.case import (
    AttachContext,
    CreateContext,
    DeleteContext,
    EnumerateContext,
    FusionCaseAPI,
    FusionCaseAPIConfig,
    RetrieveContext,
    UpdateContext,
)
from edf_fusion.server.info import FusionInfoAPI, FusionInfoAPIConfig
from edf_fusion.server.storage import (
    FusionStorage,
    FusionStorageConfig,
    get_fusion_storage,
)

_LOGGER = get_logger('server', root='test')


@dataclass(kw_only=True)
class Case(FusionCase):
    """Case"""

    value: int = 0


@dataclass(kw_only=True)
class Event(FusionEvent):
    """Event"""

    source: str = 'fusion-test'
    category: str = 'test'


@dataclass(kw_only=True)
class Storage(FusionStorage):
    """File System Storage"""

    config: FusionStorageConfig
    cases: dict[UUID, Case] = field(default_factory=dict)

    async def attach_case(
        self, case_guid: UUID, next_case_guid: UUID
    ) -> Case | None:
        case = self.cases.pop(case_guid)
        self.cases[next_case_guid] = case
        return case

    async def create_case(self, managed: bool, dct) -> Case | None:
        case = Case.from_dict(dct)
        self.cases[case.guid] = case
        return case

    async def update_case(self, case_guid: UUID, dct) -> Case | None:
        case = self.cases.get(case_guid)
        if not case:
            _LOGGER.error("case not found: %s", case_guid)
            return None
        case.update(dct)
        return case

    async def delete_case(self, case_guid: UUID) -> bool:
        """Remove case from storage"""
        return bool(self.cases.pop(case_guid, None))

    async def retrieve_case(self, case_guid: UUID) -> Case | None:
        case = self.cases.get(case_guid)
        if not case:
            _LOGGER.error("case not found: %s", case_guid)
            return None
        return case

    async def enumerate_cases(self) -> AsyncIterator[Case]:
        for case in self.cases.values():
            yield case


async def _authorize_impl(
    _request: Request, _action: Action, _identity: Identity
) -> bool:
    return True


async def _attach_case_impl(ctx: AttachContext) -> Case | None:
    """Attach case"""
    storage = get_fusion_storage(ctx.request)
    return await storage.attach_case(ctx.case_guid, ctx.next_case_guid)


async def _create_case_impl(ctx: CreateContext) -> Case | None:
    """Create case"""
    storage = get_fusion_storage(ctx.request)
    return await storage.create_case(ctx.managed, ctx.body)


async def _update_case_impl(ctx: UpdateContext) -> Case | None:
    """Update case"""
    storage = get_fusion_storage(ctx.request)
    return await storage.update_case(ctx.case_guid, ctx.body)


async def _delete_case_impl(ctx: DeleteContext) -> bool:
    """Delete case"""
    storage = get_fusion_storage(ctx.request)
    return await storage.delete_case(ctx.case_guid)


async def _retrieve_case_impl(ctx: RetrieveContext) -> Case | None:
    """Retrieve case"""
    storage = get_fusion_storage(ctx.request)
    return await storage.retrieve_case(ctx.case_guid)


async def _enumerate_cases_impl(ctx: EnumerateContext) -> list[Case]:
    """Enumerate cases"""
    storage = get_fusion_storage(ctx.request)
    return [case async for case in storage.enumerate_cases()]


async def _init_app():
    webapp = Application()
    redis = setup_redis(webapp, 'redis://localhost')
    fusion_auth_api_config = FusionAuthAPIConfig.from_dict(
        {
            'backend': {
                'strategy': 'basic',
                'basic': {
                    'users': [
                        {
                            'username': 'user',
                            'digest': '$argon2id$v=19$m=65536,t=3,p=4$QArdfPbCRCYzTcuq8i5vww$ew6a1Fzm2MNSw5wcVVe9foO4AcuT+bt7M+TAxmCH2Qk',
                            'goups': [],
                        }
                    ],
                    'groups': [],
                },
            },
            'clients': [
                {
                    'key': 'KPz6RzsTRHZEUv_ybxXUBwO3He4LriRHto33ZAkXWY4w',
                    'identity': {'username': 'client', 'groups': []},
                }
            ],
            'iron_key': 'eBcM0SvjMsOjmV7LaQLwvwkACK_ogSJitPizqWdR2mcg',
        }
    )
    fusion_auth_api = FusionAuthAPI(
        redis=redis,
        config=fusion_auth_api_config,
        authorize_impl=_authorize_impl,
    )
    fusion_auth_api.setup(webapp)
    info = Info(api='test', version='x.y.z')
    fusion_info_api_config = FusionInfoAPIConfig.from_dict(
        {'auth_required': False}
    )
    fusion_info_api = FusionInfoAPI(info=info, config=fusion_info_api_config)
    fusion_info_api.setup(webapp)
    fusion_case_api = FusionCaseAPI(
        config=FusionCaseAPIConfig.from_dict({}),
        case_cls=Case,
        attach_case_impl=_attach_case_impl,
        create_case_impl=_create_case_impl,
        update_case_impl=_update_case_impl,
        delete_case_impl=_delete_case_impl,
        retrieve_case_impl=_retrieve_case_impl,
        enumerate_cases_impl=_enumerate_cases_impl,
    )
    fusion_case_api.setup(webapp)
    storage_config = FusionStorageConfig.from_dict(
        {'directory': '/tmp/fusion/storage'}
    )
    storage = Storage(redis=redis, config=storage_config)
    storage.setup(webapp)
    return webapp


def app():
    """Application entrypoint"""
    run_app(
        _init_app(),
        host='127.0.0.1',
        port=18080,
    )


if __name__ == '__main__':
    app()
