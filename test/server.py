#!/usr/bin/env python3
"""Test Service"""

from dataclasses import dataclass

from aiohttp.web import Application, Request, run_app

from edf_fusion.concept import Case as FusionCase
from edf_fusion.concept import Event as FusionEvent
from edf_fusion.concept import Identity, Info
from edf_fusion.helper.logging import get_logger
from edf_fusion.helper.redis import setup_redis
from edf_fusion.server.auth import FusionAuthAPI, FusionAuthAPIConfig
from edf_fusion.server.case import (
    AttachContext,
    CreateContext,
    EnumerateContext,
    FusionCaseAPI,
    FusionCaseAPIConfig,
    RetrieveContext,
    UpdateContext,
)
from edf_fusion.server.info import FusionInfoAPI, FusionInfoAPIConfig

_CASES = {}
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


async def _authorize_impl(_identity: Identity, _request: Request) -> bool:
    return True


async def _attach_case_impl(ctx: AttachContext) -> Case | None:
    case = _CASES.pop(ctx.case_guid)
    _CASES[ctx.next_guid] = case
    return case


async def _create_case_impl(ctx: CreateContext) -> Case | None:
    case = Case.from_dict(ctx.body)
    _CASES[case.guid] = case
    return case


async def _update_case_impl(ctx: UpdateContext) -> Case | None:
    case = _CASES.get(ctx.case_guid)
    if not case:
        return None
    case.update(ctx.body)
    return case


async def _retrieve_case_impl(ctx: RetrieveContext) -> Case | None:
    case = _CASES.get(ctx.case_guid)
    if not case:
        return None
    return case


async def _enumerate_cases_impl(_ctx: EnumerateContext) -> list[Case]:
    return list(_CASES.values())


async def _init_app():
    webapp = Application()
    redis = setup_redis(webapp, 'redis://localhost')
    fusion_auth_api = FusionAuthAPI(
        redis=redis,
        config=FusionAuthAPIConfig.from_dict(
            {
                'backend': {
                    'strategy': 'basic',
                    'users': [
                        {
                            'username': 'test',
                            'digest': '$argon2id$v=19$m=65536,t=3,p=4$20W54XzvJwLt5nS5XzE5Iw$1LX+eQRy+QtlmdMb62xrvu72dDZ0JaG6QnCqLsFGZ1Y',
                            'goups': ['TEST'],
                        }
                    ],
                    'groups': ['TEST'],
                },
                'clients': [],
                'iron_key': 'test',
            }
        ),
        authorize_impl=_authorize_impl,
    )
    fusion_auth_api.setup(webapp)
    info = Info(api='test', version='x.y.z')
    fusion_info_api = FusionInfoAPI(
        info=info,
        config=FusionInfoAPIConfig.from_dict({'auth_required': False}),
    )
    fusion_info_api.setup(webapp)
    fusion_case_api = FusionCaseAPI(
        config=FusionCaseAPIConfig.from_dict({}),
        case_cls=Case,
        attach_case_impl=_attach_case_impl,
        create_case_impl=_create_case_impl,
        update_case_impl=_update_case_impl,
        retrieve_case_impl=_retrieve_case_impl,
        enumerate_cases_impl=_enumerate_cases_impl,
    )
    fusion_case_api.setup(webapp)
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
