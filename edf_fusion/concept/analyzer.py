"""Fusion Analyzer"""

from dataclasses import dataclass

from .abc import Concept


@dataclass(kw_only=True)
class AnalyzerInfo(Concept):
    """Fusion Analyzer Info"""

    name: str
    tags: set[str]
    version: str

    @classmethod
    def from_dict(cls, dct):
        return cls(
            name=dct['name'], tags=set(dct['tags']), version=dct['version']
        )

    def to_dict(self):
        return {
            'name': self.name,
            'tags': list(self.tags),
            'version': self.version,
        }

    def update(self, dct):
        raise NotImplementedError("Analyzer.update shall not be used")
