"""Vérification périodique des nouvelles sorties Spotify."""

import discord
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


async def check_artist(artist: dict, channel: discord.abc.Messageable, bot: discord.Client) -> bool:
    """
    Vérifie un seul artiste.

    Retourne :
      - True  → artiste traité (sortie nouvelle, pas de sortie, ou erreur non-429)
                → l'appelant doit appeler mark_checked()
      - False → 429 rencontré, rate limit activé → NE PAS marquer, stop du cycle
    """
    gid = artist["guild_id"]
    artist_id = artist["artist_id"]
    name = artist["name"]

    try:
        release = await get_latest_release(artist_id)
        if not release:
            log.debug(f"Aucun album trouvé pour '{name}'")
            return True

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

        return True

    except SpotifyException as e:
        if e.http_status == 429:
            retry_after = extract_retry_after(e)
            activate_rate_limit(retry_after, bot)
            log.warning(f"429 sur '{name}' — stop total, reprise dans {format_remaining()}")
            return False
        log.error(f"SpotifyException sur '{name}' ({artist_id}) | HTTP {e.http_status} | {e.msg}")
        return True
    except Exception as e:
        log.error(f"Erreur inattendue sur '{name}' ({artist_id}) | {type(e).__name__}: {e}")
        return True


async def do_check(bot: discord.Client, filter_name: str = None, guild_id: int = None):
    if is_rate_limited():
        log.info(f"⏭️ Cycle skippé — rate limit encore actif ({format_remaining()})")
        return

    all_artists = await storage.get_all_tracked()

    # ── Filtres optionnels (déclenchement manuel) ──────────────────────
    if guild_id is not None:
        all_artists = [a for a in all_artists if a["guild_id"] == guild_id]
    if filter_name is not None:
        all_artists = [a for a in all_artists if a["name"].lower() == filter_name.lower()]

    total = len(all_artists)
    count, maximum, pct = throttle.get_usage()
    log.info(f"🔄 Début du cycle — {total} artiste(s), ~{total * 2} requêtes prévues | Throttle : {count}/{maximum} ({pct:.0%})")

    # Cache de résolution guild/channel (évite les lookups répétés et le spam de logs)
    guild_cache: dict[int, discord.Guild | None] = {}
    channel_cache: dict[int, discord.abc.Messageable | None] = {}

    for artist in all_artists:
        if is_rate_limited():
            log.warning(f"Rate limit actif, arrêt du cycle (encore {format_remaining()})")
            return

        gid = artist["guild_id"]

        # ── Résolution guild (cache) ───────────────────────────────────
        if gid not in guild_cache:
            guild_cache[gid] = bot.get_guild(gid)
        guild = guild_cache[gid]
        if not guild:
            log.warning(f"Guild introuvable (ID={gid}), artiste '{artist['name']}' skippé")
            continue  # transitoire → pas de mark_checked, on retentera

        # ── Résolution channel (cache) ─────────────────────────────────
        if gid not in channel_cache:
            channel_cache[gid] = guild.get_channel(ANNOUNCE_CHANNEL)
        channel = channel_cache[gid]
        if not channel:
            log.error(f"Channel introuvable sur guild {gid} (ID={ANNOUNCE_CHANNEL})")
            continue  # config → pas d'appel API, pas de mark_checked

        # ── Vérification de l'artiste ──────────────────────────────────
        ok = await check_artist(artist, channel, bot)
        if not ok:
            return  # 429 → stop total, artiste non marqué (reste en tête de file)

        await storage.mark_checked(gid, artist["artist_id"])

    count, maximum, pct = throttle.get_usage()
    log.info(f"✅ Cycle terminé | Throttle : {count}/{maximum} ({pct:.0%})")