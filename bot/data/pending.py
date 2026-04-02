"""File d'attente des requêtes /spy pendant un rate limit Spotify — MySQL."""

from bot.data.database import execute, fetchone, fetchall
from bot.utils.logger import log


def _normalize_url(url: str) -> str:
    """Extrait l'artist ID d'une URL Spotify pour comparaison fiable."""
    try:
        return url.split("/artist/")[1].split("?")[0].split("/")[0]
    except (IndexError, AttributeError):
        return url


async def is_duplicate(guild_id: int, url: str) -> bool:
    """Vérifie si une requête identique (même guild + même artiste) est déjà en file."""
    rows = await fetchall(
        "SELECT url FROM queue WHERE guild_id = %s",
        (guild_id,),
    )
    artist_id = _normalize_url(url)
    return any(_normalize_url(row["url"]) == artist_id for row in rows)


async def add_to_queue(guild_id: int, user_id: int, url: str) -> bool:
    """
    Ajoute une requête à la file d'attente.
    Retourne True si ajoutée, False si doublon détecté.
    """
    if await is_duplicate(guild_id, url):
        log.debug(f"Doublon détecté dans la file : guild={guild_id}, url={url}")
        return False

    await execute(
        "INSERT INTO queue (guild_id, user_id, url) VALUES (%s, %s, %s)",
        (guild_id, user_id, url),
    )
    log.info(f"Requête ajoutée à la file : guild={guild_id}, user={user_id}, url={url}")
    return True


async def remove_entry(entry_id: int):
    """Retire une entrée de la file par son ID."""
    await execute("DELETE FROM queue WHERE id = %s", (entry_id,))


async def get_all_pending() -> list[dict]:
    """Retourne toutes les entrées en attente."""
    return await fetchall("SELECT * FROM queue ORDER BY added_at")


async def count_pending() -> int:
    """Nombre d'entrées en attente."""
    row = await fetchone("SELECT COUNT(*) AS cnt FROM queue")
    return row["cnt"] if row else 0


async def clear_queue():
    """Vide la file d'attente."""
    await execute("DELETE FROM queue")
    log.info("File d'attente vidée")