import discord
from discord import app_commands
from discord.ext import commands
from spotipy.exceptions import SpotifyException

from bot.data.storage import tracked, save_data
from bot.spotify.api import get_artist_from_url, get_latest_release
from bot.discord.client import do_check
from bot.utils.logger import log


# ─── AUTOCOMPLETE ──────────────────────────────────────────────────────────────
async def artist_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=info["name"], value=info["name"])
        for info in tracked.values()
        if current.lower() in info["name"].lower()
    ][:25]


# ─── COG ───────────────────────────────────────────────────────────────────────
class SpotifyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /track ─────────────────────────────────────────────────────────
    @app_commands.command(name="follow", description="Suivre un artiste Spotify via son lien de page")
    @app_commands.describe(url="Lien de la page Spotify de l'artiste (ex: https://open.spotify.com/artist/...)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def track(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer(ephemeral=True)

        if "/artist/" not in url:
            await interaction.followup.send(
                "❌ Lien invalide. Utilise un lien artiste Spotify.\n"
                "Ex: `https://open.spotify.com/artist/...`",
                ephemeral=True
            )
            return

        try:
            artist = await get_artist_from_url(url)
            if not artist:
                await interaction.followup.send("❌ Impossible de récupérer l'artiste.", ephemeral=True)
                return
        except SpotifyException as e:
            log.error(f"/track SpotifyException | HTTP {e.http_status} | {e.msg}")
            await interaction.followup.send(f"❌ Erreur Spotify (HTTP {e.http_status}) : {e.msg}", ephemeral=True)
            return
        except Exception as e:
            log.error(f"/track Erreur inattendue | {type(e).__name__}: {e}")
            await interaction.followup.send("❌ Erreur inattendue, consulte les logs.", ephemeral=True)
            return

        aid  = artist["id"]
        name = artist["name"]

        if aid in tracked:
            await interaction.followup.send(f"⚠️ **{name}** est déjà suivi.", ephemeral=True)
            return

        try:
            release = await get_latest_release(aid)
        except Exception as e:
            log.warning(f"/track Impossible de récupérer la dernière sortie de '{name}' | {e}")
            release = None

        tracked[aid] = {
            "name": name,
            "last_release_id": release["id"] if release else None
        }
        save_data(tracked)
        log.info(f"Artiste ajouté : {name} ({aid})")
        await interaction.followup.send(f"✅ **{name}** ajouté à la liste de suivi !", ephemeral=True)

    # ── /untrack ───────────────────────────────────────────────────────
    @app_commands.command(name="unfollow", description="Arrêter de suivre un artiste")
    @app_commands.describe(artiste="Nom de l'artiste à retirer")
    @app_commands.autocomplete(artiste=artist_autocomplete)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def untrack(self, interaction: discord.Interaction, artiste: str):
        match = next((aid for aid, info in tracked.items()
                      if info["name"].lower() == artiste.lower()), None)
        if not match:
            await interaction.response.send_message(f"❌ **{artiste}** n'est pas dans la liste.", ephemeral=True)
            return

        name = tracked[match]["name"]
        del tracked[match]
        save_data(tracked)
        log.info(f"Artiste retiré : {name} ({match})")
        await interaction.response.send_message(f"🗑️ **{name}** retiré de la liste.", ephemeral=True)

    # ── /list ──────────────────────────────────────────────────────────
    @app_commands.command(name="list", description="Voir les artistes suivis")
    async def list_artists(self, interaction: discord.Interaction):
        if not tracked:
            await interaction.response.send_message("📭 Aucun artiste suivi pour l'instant.", ephemeral=True)
            return

        lines = [f"• **{info['name']}**" for info in tracked.values()]
        embed = discord.Embed(
            title="🎧 Artistes suivis",
            description="\n".join(lines),
            color=0x1DB954
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /latest ────────────────────────────────────────────────────────
    @app_commands.command(name="latest", description="Afficher la dernière sortie connue d'un artiste suivi")
    @app_commands.describe(artiste="Nom de l'artiste")
    @app_commands.autocomplete(artiste=artist_autocomplete)
    async def latest(self, interaction: discord.Interaction, artiste: str):
        match = next((
            (aid, info) for aid, info in tracked.items()
            if info["name"].lower() == artiste.lower()
        ), None)

        if not match:
            await interaction.response.send_message(
                f"❌ **{artiste}** n'est pas dans la liste. Utilise `/list` pour voir les artistes suivis.",
                ephemeral=True
            )
            return

        aid, info = match
        url  = info.get("last_release_url")
        name = info.get("last_release_name")

        if not url:
            await interaction.response.send_message(
                f"😕 Aucune sortie connue pour **{info['name']}** pour l'instant.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(f"[{info['name']} — {name}]({url})")

# ─── SETUP (appelé par bot.load_extension) ─────────────────────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(SpotifyCog(bot))
    log.info("Cog SpotifyCog chargé")