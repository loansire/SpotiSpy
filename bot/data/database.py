"""Pool de connexions MySQL async et helpers SQL pour SpotiSpy."""

import aiomysql

from bot.config import DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME
from bot.utils.logger import log


# ─── POOL GLOBAL ───────────────────────────────────────────────────────────────
_pool: aiomysql.Pool | None = None


async def init_pool():
    """Crée le pool de connexions MySQL. À appeler une seule fois au démarrage."""
    global _pool
    _pool = await aiomysql.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        db=DB_NAME,
        minsize=1,
        maxsize=5,
        autocommit=True,
        charset="utf8mb4",
    )
    log.info(f"Pool MySQL initialisé ({DB_HOST}:{DB_PORT}/{DB_NAME})")


async def close_pool():
    """Ferme proprement le pool. À appeler à l'arrêt du bot."""
    global _pool
    if _pool:
        _pool.close()
        await _pool.wait_closed()
        _pool = None
        log.info("Pool MySQL fermé")


def _get_pool() -> aiomysql.Pool:
    """Retourne le pool ou lève une erreur si non initialisé."""
    if _pool is None:
        raise RuntimeError("Pool MySQL non initialisé — appeler init_pool() d'abord")
    return _pool


# ─── HELPERS SQL ───────────────────────────────────────────────────────────────


async def execute(sql: str, args: tuple = ()) -> int:
    """
    INSERT / UPDATE / DELETE.
    Retourne lastrowid (utile pour les INSERT AUTO_INCREMENT).
    """
    pool = _get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, args)
            return cur.lastrowid


async def fetchone(sql: str, args: tuple = ()) -> dict | None:
    """SELECT → une ligne en dict, ou None."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, args)
            return await cur.fetchone()


async def fetchall(sql: str, args: tuple = ()) -> list[dict]:
    """SELECT → liste de dicts."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, args)
            return await cur.fetchall()


async def execute_transaction(queries: list[tuple[str, tuple]]):
    """
    Exécute plusieurs requêtes dans une transaction.
    Rollback automatique en cas d'erreur.

    Args:
        queries: liste de (sql, args) à exécuter séquentiellement.
    """
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                for sql, args in queries:
                    await cur.execute(sql, args)
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise