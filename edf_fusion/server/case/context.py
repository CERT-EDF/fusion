"""Fusion Case API Context"""

from dataclasses import dataclass
from uuid import UUID

from aiohttp.web import Request

from ...concept import Identity
from ..auth import IRON_SERVER_USERNAME


@dataclass(kw_only=True)
class Context:
    """Generic context"""

    request: Request
    identity: Identity

    @property
    def managed(self):
        """Determine if request initiator is fusion server"""
        return self.identity.username == IRON_SERVER_USERNAME


@dataclass(kw_only=True)
class AttachContext(Context):
    """Attach context"""

    case_guid: UUID
    next_case_guid: UUID


@dataclass(kw_only=True)
class CreateContext(Context):
    """Create context"""

    body: dict


@dataclass(kw_only=True)
class UpdateContext(Context):
    """Update context"""

    body: dict
    case_guid: UUID


@dataclass(kw_only=True)
class DeleteContext(Context):
    """Delete context"""

    case_guid: UUID


@dataclass(kw_only=True)
class RetrieveContext(Context):
    """Retrieve context"""

    case_guid: UUID


@dataclass(kw_only=True)
class EnumerateContext(Context):
    """Enumerate context"""
