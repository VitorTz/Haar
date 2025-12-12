from asyncpg import create_pool, Pool, Connection
from src.migrate import db_migrate
from dotenv import load_dotenv
from typing import Callable
import psycopg
import os


load_dotenv()


db_pool: Pool = None


async def db_init() -> None:
    global db_pool
    db_pool = await create_pool(os.getenv("DATABASE_URL"), min_size=5, max_size=20, statement_cache_size=0)
    async with db_pool.acquire() as conn:
        await db_migrate(conn)


def db_instance() -> psycopg.Connection:
    conn = psycopg.connect(os.getenv("DATABASE_URL"))
    return conn


def get_db_pool() -> Pool:
    global db_pool
    return db_pool


async def db_close() -> None:
    await db_pool.close()


async def get_db():
    async with db_pool.acquire() as conn:
        yield conn


async def db_count(table: str, conn: Connection) -> int:
    r = await conn.fetchrow(f"SELECT COUNT(*) AS total FROM {table};")
    return dict(r)['total']


async def db_version(conn: Connection) -> str:
    r = await conn.fetchrow("SELECT version()")    
    return r['version']


async def db_reset(migration: Callable[[Connection], None], conn: Connection) -> None:
    
    queries = [
        "DROP TABLE IF EXISTS users CASCADE;",
        "DROP TABLE IF EXISTS user_session_tokens CASCADE;",
        "DROP TABLE IF EXISTS user_login_attempts CASCADE;",
        "DROP TABLE IF EXISTS domains CASCADE;",
        "DROP TABLE IF EXISTS urls CASCADE;",
        "DROP TABLE IF EXISTS user_urls CASCADE;",
        "DROP TABLE IF EXISTS url_tags CASCADE;",
        "DROP TABLE IF EXISTS url_tag_relations CASCADE;",
        "DROP TABLE IF EXISTS url_analytics CASCADE;",
        "DROP TABLE IF EXISTS logs CASCADE;",
        "DROP TABLE IF EXISTS time_perf CASCADE;",
        "DROP TABLE IF EXISTS rate_limit_logs CASCADE;",
        "DROP TABLE IF EXISTS logs CASCADE;",
        "DROP MATERIALIZED VIEW IF EXISTS mv_dashboard CASCADE;"
    ]

    await conn.execute("SELECT pg_advisory_lock(9999);")

    try:
        async with conn.transaction():
            for q in queries: await conn.execute(q)
            await migration(conn)
    finally:
        await conn.execute("SELECT pg_advisory_unlock(9999);")

