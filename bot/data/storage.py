"""Accès aux données artistes/abonnements — MySQL via aiomysql."""

from bot.data.database import execute, fetchone, fetchall, execute_transaction
from bot.utils.logger import log


# ─── GUILDS ────────────────────────────────────────────────────────────────────


async def ensure_guild(guild_id: int):
    """Crée le guild s'il n'existe pas (INSERT IGNORE)."""
    await execute("INSERT IGNORE INTO guilds (guild_id) VALUES (%s)", (guild_id,))


# ─── LECTURE ───────────────────────────────────────────────────────────────────


async def get_artist(guild_id: int, artist_id: str) -> dict | None:
    """Retourne un artiste d'un guild, ou None."""
    return await fetchone(
        "SELECT * FROM artists WHERE guild_id = %s AND artist_id = %s",
        (guild_id, artist_id),
    )


async def get_guild_artists(guild_id: int) -> list[dict]:
    """Tous les artistes d'un guild."""
    return await fetchall(
        "SELECT * FROM artists WHERE guild_id = %s ORDER BY name",
        (guild_id,),
    )


async def get_all_tracked() -> list[dict]:
    """Tous les artistes de tous les guilds (pour le checker)."""
    return await fetchall("SELECT * FROM artists ORDER BY guild_id, name")


async def get_subscribers(guild_id: int, artist_id: str) -> list[int]:
    """Liste des user_id abonnés à un artiste."""
    rows = await fetchall(
        "SELECT user_id FROM subscriptions WHERE guild_id = %s AND artist_id = %s",
        (guild_id, artist_id),
    )
    return [row["user_id"] for row in rows]


async def is_subscribed(guild_id: int, artist_id: str, user_id: int) -> bool:
    """Vérifie si un utilisateur est abonné à un artiste."""
    row = await fetchone(
        "SELECT 1 FROM subscriptions WHERE guild_id = %s AND artist_id = %s AND user_id = %s",
        (guild_id, artist_id, user_id),
    )
    return row is not None


# ─── ÉCRITURE — ARTISTES ──────────────────────────────────────────────────────


def _extract_image(artist: dict) -> str | None:
    """Extrait la plus petite image de profil d'un artiste Spotify."""
    images = artist.get("images", [])
    if not images:
        return None
    sorted_imgs = sorted(images, key=lambda x: x.get("height", 0))
    return sorted_imgs[0]["url"]


async def add_artist(
    guild_id: int,
    artist: dict,
    release: dict | None,
    notify_role: bool = False,
) -> bool:
    """
    Ajoute un artiste dans un guild (INSERT IGNORE).
    Retourne True si créé, False s'il existait déjà.
    """
    await ensure_guild(guild_id)

    image = _extract_image(artist)
    result = await execute(
        """
        INSERT IGNORE INTO artists
            (guild_id, artist_id, name, image_url,
             last_release_id, last_release_name, last_release_url, notify_role)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            guild_id,
            artist["id"],
            artist["name"],
            image,
            release["id"] if release else None,
            release["name"] if release else None,
            release["external_urls"]["spotify"] if release else None,
            notify_role,
        ),
    )
    created = result != 0
    if created:
        log.info(f"[Guild {guild_id}] Artiste ajouté : {artist['name']}")
    return created


async def update_release(guild_id: int, artist_id: str, release: dict):
    """Met à jour la dernière sortie d'un artiste."""
    await execute(
        """
        UPDATE artists
        SET last_release_id = %s, last_release_name = %s, last_release_url = %s
        WHERE guild_id = %s AND artist_id = %s
        """,
        (
            release["id"],
            release["name"],
            release["external_urls"]["spotify"],
            guild_id,
            artist_id,
        ),
    )


async def update_image(guild_id: int, artist_id: str, image_url: str):
    """Met à jour l'image de profil d'un artiste (si absente)."""
    await execute(
        """
        UPDATE artists SET image_url = %s
        WHERE guild_id = %s AND artist_id = %s AND image_url IS NULL
        """,
        (image_url, guild_id, artist_id),
    )


async def set_notify_role(guild_id: int, artist_id: str, enabled: bool):
    """Active ou désactive le ping rôle pour un artiste."""
    await execute(
        "UPDATE artists SET notify_role = %s WHERE guild_id = %s AND artist_id = %s",
        (enabled, guild_id, artist_id),
    )


# ─── ÉCRITURE — ABONNEMENTS ───────────────────────────────────────────────────


async def add_subscriber(guild_id: int, artist_id: str, user_id: int) -> bool:
    """
    Ajoute un abonné (INSERT IGNORE).
    Retourne True si ajouté, False si déjà abonné.
    """
    result = await execute(
        "INSERT IGNORE INTO subscriptions (guild_id, artist_id, user_id) VALUES (%s, %s, %s)",
        (guild_id, artist_id, user_id),
    )
    return result != 0


async def remove_subscriber(guild_id: int, artist_id: str, user_id: int):
    """Retire un abonné."""
    await execute(
        "DELETE FROM subscriptions WHERE guild_id = %s AND artist_id = %s AND user_id = %s",
        (guild_id, artist_id, user_id),
    )


# ─── NETTOYAGE ─────────────────────────────────────────────────────────────────


async def cleanup_artist(guild_id: int, artist_id: str):
    """
    Supprime un artiste s'il n'a plus d'abonnés ni de notify_role.
    Supprime le guild s'il n'a plus d'artistes.
    """
    artist = await get_artist(guild_id, artist_id)
    if not artist:
        return

    subs = await get_subscribers(guild_id, artist_id)
    if subs or artist["notify_role"]:
        return

    await execute(
        "DELETE FROM artists WHERE guild_id = %s AND artist_id = %s",
        (guild_id, artist_id),
    )
    log.info(f"[Guild {guild_id}] Artiste supprimé (plus d'abonnés ni de ping rôle) : {artist['name']}")

    # Supprimer le guild s'il est vide
    remaining = await fetchone(
        "SELECT 1 FROM artists WHERE guild_id = %s LIMIT 1",
        (guild_id,),
    )
    if not remaining:
        await execute("DELETE FROM guilds WHERE guild_id = %s", (guild_id,))
        log.info(f"[Guild {guild_id}] Guild supprimé (plus d'artistes)")