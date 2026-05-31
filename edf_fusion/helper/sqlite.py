"""Fusion Core SQLite Helper"""

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from aiosqlite import Connection, Row, connect

from .logging import get_logger
from .serializing import dump_json
from ..concept import Concept

_LOGGER = get_logger('helper.redis')


@dataclass(kw_only=True)
class SQLiteDatabase:
    """SQLite Database"""

    filepath: Path
    prepare_db: Callable[['SQLiteDatabase'], Awaitable[None]] | None = None
    connection: Connection | None = None

    async def context(self, *args, **kwargs):
        """Database execution context"""
        _LOGGER.info("connecting to sqlite database %s", self.filepath)
        # startup
        self.connection = await connect(self.filepath, autocommit=True)
        self.connection.row_factory = Row
        _LOGGER.info("preparing sqlite database %s", self.filepath)
        if self.prepare_db:
            await self.prepare_db(self)
        # handover
        yield
        # cleanup
        await self.connection.close()
        self.connection = None
        _LOGGER.info("ptr storage cleaned up.")

    async def execute(
        self, statement: str, parameters: dict | None = None
    ) -> int:
        """Execute statement and get row count when applicable"""
        row_count = -1
        parameters = parameters or {}
        async with self.connection.execute(statement, parameters) as cursor:
            row_count = cursor.rowcount
        return row_count

    async def fetchone(
        self, statement: str, parameters: dict | None = None
    ) -> Row | None:
        """Execute statement and get one row"""
        parameters = parameters or {}
        async with self.connection.execute(statement, parameters) as cursor:
            return await cursor.fetchone()

    async def fetchmany(
        self, statement: str, parameters: dict | None = None
    ) -> AsyncIterator[Row]:
        """Execute statement and get rows"""
        parameters = parameters or {}
        async with self.connection.execute(statement, parameters) as cursor:
            async for row in cursor:
                yield row


def parameters_from_concept(concept: Concept) -> dict:
    """Generate parameters from Fusion Concept instance"""
    dct = concept.to_dict()
    parameters = {}
    for key, val in dct.items():
        if isinstance(val, (int, float, str, bytes)) or val is None:
            parameters[key] = val
            continue
        if isinstance(val, (list, dict)):
            parameters[key] = dump_json(val)
            continue
        if isinstance(val, bool):
            parameters[key] = 1 if val else 0
    return parameters
