"""Vérification périodique des nouvelles sorties Spotify."""

import asyncio
import discord
from itertools import groupby
from operator import itemgetter
from spotipy.exceptions import SpotifyException

from bot.config import ANNOUNCE_CHANNEL
from bot.data import storage
from bot.spotify.api import get_latest_release
from bot.spotify.rate_limit import is_rate_limited, activate_rate_limit, extract_retry_after, format_remaining
from bot.spotify.throttle import throttle
from bot.utils.logger import log


async def build_mentions(guild_id: int, artist_id: str) -> str:
    """Construit la chaîne de mentions pour un artiste."""
    subs = await storage.get_subscribers(guild_id, artist_id)
    if not subs:
        return ""
    return " ".join(f"<@{uid}>" for uid in subs)


async def check_guild(guild: discord.Guild, bot: discord.Client, artists: list[dict], filter_name: str = None):
    gid = guild.id
    channel = guild.get_channel(ANNOUNCE_CHANNEL)

    if not channel:
        log.error(f"Channel introuvable sur guild {gid} (ID={ANNOUNCE_CHANNEL})")
        return

    targets = [
        a for a in artists
        if filter_name is None or a["name"].lower() == filter_name.lower()
    ]

    log.info(f"[Guild {gid}] Vérification de {len(targets)} artiste(s)...")

    for artist in targets:
        if is_rate_limited():
            log.warning(f"[Guild {gid}] Rate limit actif, arrêt du cycle (encore {format_remaining()})")
            return

        artist_id = artist["artist_id"]
        name = artist["name"]

        try:
            release = await get_latest_release(artist_id)
            if not release:
                log.debug(f"Aucun album trouvé pour '{name}'")
                continue

            if release["id"] != artist.get("last_release_id"):
                await storage.update_release(gid, artist_id, release)

                mentions = await build_mentions(gid, artist_id)
                msg = f"{mentions} Nouvelle sortie !\n" if mentions else "Nouvelle sortie !\n"
                await channel.send(
                    msg + f"[{name} — {release['name']}]({release['external_urls']['spotify']})"
                )
                log.info(f"🎶 [Guild {gid}] Nouvelle sortie : {name} — {release['name']}")
            else:
                log.debug(f"Pas de nouvelle sortie pour '{name}' — ID inchangé")

        except SpotifyException as e:
            if e.http_status == 429:
                retry_after = extract_retry_after(e)
                activate_rate_limit(retry_after, bot)
                log.warning(f"429 sur '{name}' — stop total, reprise dans {format_remaining()}")
                return
            log.error(f"SpotifyException sur '{name}' ({artist_id}) | HTTP {e.http_status} | {e.msg}")
        except Exception as e:
            log.error(f"Erreur inattendue sur '{name}' ({artist_id}) | {type(e).__name__}: {e}")


async def do_check(bot: discord.Client, filter_name: str = None, guild_id: int = None):
    if is_rate_limited():
        log.info(f"⏭️ Cycle skippé — rate limit encore actif ({format_remaining()})")
        return

    all_artists = await storage.get_all_tracked()
    total = len(all_artists)
    count, maximum, pct = throttle.get_usage()
    log.info(f"🔄 Début du cycle — {total} artiste(s), ~{total * 2} requêtes prévues | Throttle : {count}/{maximum} ({pct:.0%})")

    # ── Grouper par guild_id ───────────────────────────────────────────
    sorted_artists = sorted(all_artists, key=itemgetter("guild_id"))
    grouped = groupby(sorted_artists, key=itemgetter("guild_id"))

    for gid, guild_artists in grouped:
        if guild_id is not None and gid != guild_id:
            continue

        if is_rate_limited():
            return

        guild = bot.get_guild(gid)
        if not guild:
            log.warning(f"Guild introuvable (ID={gid}), skipped")
            continue

        await check_guild(guild, bot, list(guild_artists), filter_name=filter_name)

    count, maximum, pct = throttle.get_usage()
    log.info(f"✅ Cycle terminé | Throttle : {count}/{maximum} ({pct:.0%})")