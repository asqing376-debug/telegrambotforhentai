"""
轻量 SQLite 持久化：跟踪已处理画廊、爬取偏移。
"""
import os
import aiosqlite
from datetime import datetime, timezone

from loguru import logger
from config.config import cfg

_db_path: str = None
_conn: aiosqlite.Connection = None


async def init_db():
    """初始化数据库连接并建表。"""
    global _db_path, _conn
    _db_path = cfg.get("db_path") or "./data/bot.db"
    os.makedirs(os.path.dirname(os.path.abspath(_db_path)), exist_ok=True)
    _conn = await aiosqlite.connect(_db_path)
    await _conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_galleries (
            gid        TEXT PRIMARY KEY,
            token      TEXT NOT NULL,
            source     TEXT NOT NULL DEFAULT 'manual',
            processed_at TEXT NOT NULL
        )
    """)
    await _conn.execute("""
        CREATE TABLE IF NOT EXISTS crawl_offsets (
            source_name TEXT PRIMARY KEY,
            last_gid    TEXT,
            last_page   INTEGER DEFAULT 0,
            updated_at  TEXT NOT NULL
        )
    """)
    await _conn.commit()
    logger.info(f"数据库已初始化: {_db_path}")


async def close_db():
    global _conn
    if _conn:
        await _conn.close()
        _conn = None


async def is_processed(gid: str) -> bool:
    async with _conn.execute(
        "SELECT 1 FROM processed_galleries WHERE gid = ?", (gid,)
    ) as cursor:
        return await cursor.fetchone() is not None


async def mark_processed(gid: str, token: str, source: str = "manual"):
    now = datetime.now(timezone.utc).isoformat()
    await _conn.execute(
        "INSERT OR IGNORE INTO processed_galleries (gid, token, source, processed_at) VALUES (?, ?, ?, ?)",
        (gid, token, source, now),
    )
    await _conn.commit()


async def get_offset(source_name: str) -> dict | None:
    async with _conn.execute(
        "SELECT last_gid, last_page, updated_at FROM crawl_offsets WHERE source_name = ?",
        (source_name,),
    ) as cursor:
        row = await cursor.fetchone()
        if row:
            return {"last_gid": row[0], "last_page": row[1], "updated_at": row[2]}
        return None


async def set_offset(source_name: str, last_gid: str = None, last_page: int = 0):
    now = datetime.now(timezone.utc).isoformat()
    await _conn.execute(
        """INSERT INTO crawl_offsets (source_name, last_gid, last_page, updated_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(source_name)
           DO UPDATE SET last_gid = excluded.last_gid,
                         last_page = excluded.last_page,
                         updated_at = excluded.updated_at""",
        (source_name, last_gid, last_page, now),
    )
    await _conn.commit()
