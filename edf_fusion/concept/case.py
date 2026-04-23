"""Fusion Case"""

from dataclasses import dataclass, field
from typing import Type
from uuid import UUID, uuid4

from ..helper.datetime import (
    datetime,
    from_iso,
    from_iso_or_none,
    to_iso,
    to_iso_or_none,
    utcnow,
)
from .abc import Concept


@dataclass(kw_only=True)
class Case(Concept):
    """Fusion Case"""

    guid: UUID = field(default_factory=uuid4)
    managed: bool = False
    created: datetime = field(default_factory=utcnow)
    updated: datetime | None = None
    closed: datetime | None = None
    tsid: str | None
    name: str
    description: str
    acs: set[str] = field(default_factory=set)
    acs_ro: set[str] = field(default_factory=set)
    webhooks: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, dct):
        return cls(
            guid=UUID(dct['guid']),
            managed=dct['managed'],
            created=from_iso(dct['created']),
            updated=from_iso_or_none(dct['updated']),
            closed=from_iso_or_none(dct['closed']),
            tsid=dct['tsid'],
            name=dct['name'],
            description=dct['description'],
            acs=set(dct['acs']),
            acs_ro=set(dct.get('acs_ro', [])),
            webhooks=dct.get('webhooks', []),
        )

    def to_dict(self):
        return {
            'guid': str(self.guid),
            'managed': self.managed,
            'created': to_iso(self.created),
            'updated': to_iso_or_none(self.updated),
            'closed': to_iso_or_none(self.closed),
            'tsid': self.tsid,
            'name': self.name,
            'description': self.description,
            'acs': list(sorted(self.acs)),
            'acs_ro': list(sorted(self.acs_ro)),
            'webhooks': self.webhooks,
        }

    def update(self, dct):
        # guid cannot be updated
        # managed cannot be updated
        # created cannot be updated
        closed = (
            from_iso_or_none(dct['closed']) if 'closed' in dct else self.closed
        )
        if self.closed and closed:
            raise ValueError("cannot update a closed cased!")
        self.updated = utcnow()
        self.closed = closed
        self.tsid = dct.get('tsid', self.tsid)
        self.name = dct.get('name', self.name)
        self.description = dct.get('description', self.description)
        self.acs = set(dct.get('acs', self.acs))
        self.acs_ro = set(dct.get('acs_ro', self.acs_ro))
        self.webhooks = dct.get('webhooks', self.webhooks)


CaseType = Type[Case]
