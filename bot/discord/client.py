import asyncio
import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.config import CHECK_INTERVAL_H, STARTUP_DELAY_S
from bot.data.storage import tracked
from bot.data.queue import queue
from bot.spotify.checker import do_check
from bot.utils.logger import log

# ─── BOT INSTANCE ─────────────────────────────────────────────────────────────
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


# ─── LOOP ─────────────────────────────────────────────────────────────────────
@tasks.loop(hours=CHECK_INTERVAL_H)
async def check_releases():
    await do_check(bot)


@check_releases.before_loop
async def before_check():
    await bot.wait_until_ready()
    log.info(f"Attente de {STARTUP_DELAY_S}s avant le premier cycle...")
    await asyncio.sleep(STARTUP_DELAY_S)


# ─── EVENTS ────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    # Exposer la task loop pour que rate_limit.py puisse la stop/restart
    bot._check_releases_task = check_releases

    cmds = bot.tree.get_commands()
    for cmd in cmds:
        log.info(f"Commande enregistrée : /{cmd.name}")

    synced = await bot.tree.sync()
    log.info(f"Sync terminé : {len(synced)} commande(s) synchronisées")

    # Traiter la file résiduelle (crash précédent) avant de lancer le cycle
    if queue:
        log.info(f"📋 {len(queue)} requête(s) en file d'attente au démarrage, traitement...")
        from bot.spotify.rate_limit import _process_queue
        await _process_queue()

    check_releases.start()
    total = sum(len(a) for a in tracked.values())
    log.info(f"Bot connecté en tant que {bot.user} | {len(tracked)} guild(s) | {total} artiste(s) suivis")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("🚫 Tu n'as pas la permission d'utiliser cette commande.", ephemeral=True)
    elif isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(f"⏳ Cooldown — réessaie dans {error.retry_after:.0f}s.", ephemeral=True)
    else:
        log.error(f"Erreur commande /{interaction.command.name if interaction.command else '?'}: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ Erreur : {error}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Erreur : {error}", ephemeral=True)