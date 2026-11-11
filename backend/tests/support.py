from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

import asyncpg
from sqlalchemy.engine import URL


@asynccontextmanager
async def disposable_database(url: URL) -> AsyncIterator[URL]:
    """Create/drop only a randomly generated database; never clear the application DB."""
    name = f"schemeguard_{uuid4().hex}_test"
    connection = await asyncpg.connect(
        host=url.host,
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        database="postgres",
        timeout=10,
    )
    try:
        await connection.execute(f'CREATE DATABASE "{name}"')
        try:
            yield url.set(database=name)
        finally:
            await connection.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
    finally:
        await connection.close()
