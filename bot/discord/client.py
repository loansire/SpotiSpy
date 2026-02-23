import asyncio

import discord
from discord import app_commands
from discord.ext import commands, tasks
from spotipy.exceptions import SpotifyException

from bot.config import ANNOUNCE_CHANNEL, NOTIFY_ROLE_ID, CHECK_INTERVAL_H, STARTUP_DELAY_S, SLEEP_THRESHOLD
from bot.data.storage import tracked, save_data
from bot.spotify.api import get_latest_release
from bot.utils.logger import log

# ─── BOT INSTANCE ─────────────────────────────────────────────────────────────
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


# ─── CONSTRUCTION DES MENTIONS ─────────────────────────────────────────────────
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


# ─── VÉRIFICATION DES SORTIES ─────────────────────────────────────────────────
async def do_check(filter_name: str = None, guild_id: int = None):
    """Vérifie les nouvelles sorties pour tous les guilds (ou un seul si guild_id fourni)."""

    # Sélection des guilds à vérifier
    guild_ids = [str(guild_id)] if guild_id else list(tracked.keys())

    for gid in guild_ids:
        guild_data = tracked.get(gid, {})
        if not guild_data:
            continue

        guild = bot.get_guild(int(gid))
        if not guild:
            log.warning(f"Guild introuvable (ID={gid}), skipped")
            continue

        channel = guild.get_channel(ANNOUNCE_CHANNEL)
        if not channel:
            log.error(f"Channel introuvable sur guild {gid} (ID={ANNOUNCE_CHANNEL})")
            continue

        targets = {
            aid: info for aid, info in guild_data.items()
            if filter_name is None or info["name"].lower() == filter_name.lower()
        }

        use_sleep = len(targets) >= SLEEP_THRESHOLD
        log.info(f"[Guild {gid}] Vérification de {len(targets)} artiste(s){'  — délai 1s activé' if use_sleep else ''}...")

        for artist_id, info in list(targets.items()):
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
                    retry_after = int(e.headers.get("Retry-After", 3600)) if e.headers else 3600
                    log.warning(f"Rate limit 429 sur '{info['name']}' — retry dans ~{retry_after}s, cycle abandonné")
                    return
                log.error(f"SpotifyException sur '{info['name']}' ({artist_id}) | HTTP {e.http_status} | {e.msg}")
            except Exception as e:
                log.error(f"Erreur inattendue sur '{info['name']}' ({artist_id}) | {type(e).__name__}: {e}")


@tasks.loop(hours=CHECK_INTERVAL_H)
async def check_releases():
    log.info("Début du cycle de vérification...")
    await do_check()
    log.info("Cycle terminé.")


@check_releases.before_loop
async def before_check():
    await bot.wait_until_ready()
    log.info(f"Attente de {STARTUP_DELAY_S}s avant le premier cycle...")
    await asyncio.sleep(STARTUP_DELAY_S)


# ─── EVENTS ────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    await bot.tree.sync()
    check_releases.start()
    total = sum(len(a) for a in tracked.values())
    log.info(f"Bot connecté en tant que {bot.user} | {len(tracked)} guild(s) | {total} artiste(s) suivis")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("🚫 Tu n'as pas la permission.", ephemeral=True)
    else:
        log.error(f"Erreur commande /{interaction.command.name if interaction.command else '?'}: {error}")
        await interaction.response.send_message(f"❌ Erreur : {error}", ephemeral=True)