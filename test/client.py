#!/usr/bin/env python3
"""Test Client"""

from asyncio import CancelledError, run

from aiohttp import ClientConnectorError, ClientPayloadError, ClientSession
from yarl import URL

from edf_fusion.client import (
    FusionAuthAPIClient,
    FusionCaseAPIClient,
    FusionClient,
    FusionClientConfig,
    FusionInfoAPIClient,
    create_session,
)
from edf_fusion.concept import Case
from edf_fusion.helper.logging import get_logger

_LOGGER = get_logger('client', root='test')


def _log_failure():
    _LOGGER.critical("test failure!")


async def _web_login(fusion_client: FusionClient):
    fusion_auth_api_client = FusionAuthAPIClient(fusion_client=fusion_client)
    await fusion_auth_api_client.login('user', 'user')
    identity = await fusion_auth_api_client.is_logged()
    _LOGGER.info("identity: %s", identity)


async def _playbook(fusion_client: FusionClient):
    _LOGGER.info("starting playbook")
    fusion_case_api_client = FusionCaseAPIClient(
        case_cls=Case, fusion_client=fusion_client
    )
    fusion_info_api_client = FusionInfoAPIClient(fusion_client=fusion_client)
    info = await fusion_info_api_client.info()
    _LOGGER.info("retrieved info: %s", info)
    case = await fusion_case_api_client.create_case(
        Case(
            managed=True,
            tsid=None,
            name='test case',
            description='test description',
        )
    )
    if not case:
        _log_failure()
        return
    _LOGGER.info("created case: %s", case)
    case.tsid = '#00000000'
    case = await fusion_case_api_client.update_case(case)
    if not case:
        _log_failure()
        return
    _LOGGER.info("updated case: %s", case)
    case = await fusion_case_api_client.retrieve_case(case.guid)
    if not case:
        _log_failure()
        return
    _LOGGER.info("retrieved case: %s", case)
    cases = await fusion_case_api_client.enumerate_cases()
    if not cases:
        _log_failure()
        return
    _LOGGER.info("enumerated cases: %s", cases)


def _create_web_client(api_url: URL) -> tuple[ClientSession, FusionClient]:
    config = FusionClientConfig(api_url=api_url)
    session = create_session(config, unsafe=True)
    return session, FusionClient(config=config, session=session)


def _create_api_client(api_url: URL) -> tuple[ClientSession, FusionClient]:
    config = FusionClientConfig(
        api_url=api_url, api_key='KPz6RzsTRHZEUv_ybxXUBwO3He4LriRHto33ZAkXWY4w'
    )
    session = create_session(config, unsafe=True)
    return session, FusionClient(config=config, session=session)


def _create_iron_client(api_url: URL) -> tuple[ClientSession, FusionClient]:
    config = FusionClientConfig(
        api_url=api_url, api_key='eBcM0SvjMsOjmV7LaQLwvwkACK_ogSJitPizqWdR2mcg'
    )
    session = create_session(config, unsafe=True)
    return session, FusionClient(config=config, session=session)


async def app():
    """Application entrypoint"""
    api_url = URL('http://127.0.0.1:18080')
    wc_session, wc_client = _create_web_client(api_url)
    ac_session, ac_client = _create_api_client(api_url)
    ir_session, ir_client = _create_iron_client(api_url)
    async with wc_session, ac_session, ir_session:
        try:
            await _web_login(wc_client)
            await _playbook(wc_client)
            await _playbook(ac_client)
            await _playbook(ir_client)
        except CancelledError:
            _LOGGER.info("process terminated.")
        except ClientPayloadError:
            _LOGGER.info("server disconnected")
        except ClientConnectorError:
            _LOGGER.info("cannot connect to server")


if __name__ == '__main__':
    run(app())
