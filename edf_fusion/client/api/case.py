"""Fusion Case API Client"""

from dataclasses import dataclass
from uuid import UUID

from ...concept import Case, CaseType
from ...helper.logging import get_logger
from ..impl import FusionClient

_LOGGER = get_logger('client.api.case')


@dataclass(kw_only=True)
class FusionCaseAPIClient:
    """Fusion Case API Client"""

    case_cls: CaseType
    fusion_client: FusionClient

    async def attach_case(
        self, case_guid: UUID, next_case_guid: UUID
    ) -> Case | None:
        """Attach a case"""
        _LOGGER.info("attaching case %s (next=%s)", case_guid, next_case_guid)
        endpoint = f'/api/case/{case_guid}/attach/{next_case_guid}'
        return await self.fusion_client.put(
            endpoint, concept_cls=self.case_cls
        )

    async def create_case(self, case: Case) -> Case | None:
        """Create a case"""
        _LOGGER.info("creating case %s", case.guid)
        endpoint = '/api/case'
        return await self.fusion_client.post(
            endpoint, concept=case, concept_cls=self.case_cls
        )

    async def update_case(self, case: Case) -> Case | None:
        """Update an existing case"""
        _LOGGER.info("updating case %s", case.guid)
        endpoint = f'/api/case/{case.guid}'
        return await self.fusion_client.put(
            endpoint, concept=case, concept_cls=self.case_cls
        )

    async def delete_case(self, case_guid: UUID) -> bool:
        """Delete an existing case"""
        _LOGGER.info("deleting case %s", case_guid)
        endpoint = f'/api/case/{case_guid}'
        return await self.fusion_client.delete(endpoint)

    async def retrieve_case(self, case_guid: UUID) -> Case | None:
        """Retrieve case information"""
        _LOGGER.info("retrieving case %s", case_guid)
        endpoint = f'/api/case/{case_guid}'
        return await self.fusion_client.get(
            endpoint, concept_cls=self.case_cls
        )

    async def enumerate_cases(self) -> list[Case]:
        """Enumerate cases"""
        _LOGGER.info("enumerating cases")
        endpoint = '/api/cases'
        return await self.fusion_client.get(
            endpoint, concept_cls=self.case_cls
        )
