import asyncio
import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.config import CHECK_INTERVAL_H, STARTUP_DELAY_S
from bot.data.storage import tracked
from bot.spotify.checker import do_check
from bot.utils.logger import log

# ─── BOT INSTANCE ─────────────────────────────────────────────────────────────
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


# ─── LOOP ─────────────────────────────────────────────────────────────────────
@tasks.loop(hours=CHECK_INTERVAL_H)
async def check_releases():
    log.info("Début du cycle de vérification...")
    await do_check(bot)
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