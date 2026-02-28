import asyncio
import discord
from spotipy.exceptions import SpotifyException

from bot.config import ANNOUNCE_CHANNEL, NOTIFY_ROLE_ID, SLEEP_THRESHOLD
from bot.data.storage import tracked, save_data
from bot.spotify.api import get_latest_release
from bot.spotify.rate_limit import is_rate_limited, activate_rate_limit, extract_retry_after, format_remaining
from bot.utils.logger import log


def build_mentions(info: dict, guild: discord.Guild) -> str:
    mentions = []
    for uid in info.get("subscribers", []):
        mentions.append(f"<@{uid}>")
    if info.get("notify_role"):
        role = guild.get_role(NOTIFY_ROLE_ID)
        if role:
            mentions.append(role.mention)
        else:
            log.warning(f"Rôle introuvable (ID={NOTIFY_ROLE_ID}), ping rôle ignoré")
    return " ".join(mentions) if mentions else ""


async def check_guild(guild: discord.Guild, bot: discord.Client, filter_name: str = None):
    gid        = str(guild.id)
    guild_data = tracked.get(gid, {})
    channel    = guild.get_channel(ANNOUNCE_CHANNEL)

    if not channel:
        log.error(f"Channel introuvable sur guild {gid} (ID={ANNOUNCE_CHANNEL})")
        return

    targets = {
        aid: info for aid, info in guild_data.items()
        if filter_name is None or info["name"].lower() == filter_name.lower()
    }

    use_sleep = len(targets) >= SLEEP_THRESHOLD
    log.info(f"[Guild {gid}] Vérification de {len(targets)} artiste(s){'  — délai 1s activé' if use_sleep else ''}...")

    for artist_id, info in list(targets.items()):
        if is_rate_limited():
            log.warning(f"[Guild {gid}] Rate limit actif, arrêt du cycle (encore {format_remaining()})")
            return

        try:
            release = await get_latest_release(artist_id)
            if not release:
                log.debug(f"Aucun album trouvé pour '{info['name']}'")
                if use_sleep:
                    await asyncio.sleep(1)
                continue

            if release["id"] != info.get("last_release_id"):
                tracked[gid][artist_id]["last_release_id"]   = release["id"]
                tracked[gid][artist_id]["last_release_name"] = release["name"]
                tracked[gid][artist_id]["last_release_url"]  = release["external_urls"]["spotify"]
                save_data(tracked)

                mentions = build_mentions(info, guild)
                msg = f"{mentions} Nouvelle sortie !\n" if mentions else "Nouvelle sortie !\n"
                await channel.send(
                    msg + f"[{info['name']} — {release['name']}]({release['external_urls']['spotify']})"
                )
                log.info(f"🎶 [Guild {gid}] Nouvelle sortie : {info['name']} — {release['name']}")
            else:
                log.debug(f"Pas de nouvelle sortie pour '{info['name']}' — ID inchangé")

            if use_sleep:
                await asyncio.sleep(1)

        except SpotifyException as e:
            if e.http_status == 429:
                retry_after = extract_retry_after(e)
                activate_rate_limit(retry_after, bot)
                log.warning(f"429 sur '{info['name']}' — stop total, reprise dans {format_remaining()}")
                return
            log.error(f"SpotifyException sur '{info['name']}' ({artist_id}) | HTTP {e.http_status} | {e.msg}")
        except Exception as e:
            log.error(f"Erreur inattendue sur '{info['name']}' ({artist_id}) | {type(e).__name__}: {e}")


async def do_check(bot: discord.Client, filter_name: str = None, guild_id: int = None):
    if is_rate_limited():
        log.info(f"⏭️ Cycle skippé — rate limit encore actif ({format_remaining()})")
        return

    guild_ids = [guild_id] if guild_id else [int(gid) for gid in tracked.keys()]

    for gid in guild_ids:
        # Stop immédiat si un 429 a été déclenché pendant ce cycle
        if is_rate_limited():
            return

        guild = bot.get_guild(gid)
        if not guild:
            log.warning(f"Guild introuvable (ID={gid}), skipped")
            continue
        await check_guild(guild, bot, filter_name=filter_name)