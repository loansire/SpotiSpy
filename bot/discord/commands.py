import discord
from discord import app_commands
from discord.ext import commands
from spotipy.exceptions import SpotifyException

from bot.data.storage import tracked, save_data, add_artist, cleanup_artist
from bot.spotify.api import get_artist_from_url, get_latest_release
from bot.utils.autocomplete import artist_autocomplete, subscribed_autocomplete
from bot.utils.logger import log

class SpotifyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /follow ────────────────────────────────────────────────────────
    @app_commands.command(name="spy", description="S'abonner aux alertes d'un artiste Spotify")
    @app_commands.describe(url="Lien de la page Spotify de l'artiste")
    async def follow(self, interaction: discord.Interaction, url: str):
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
            log.error(f"`/spy` SpotifyException | HTTP {e.http_status} | {e.msg}")
            await interaction.followup.send(f"❌ Erreur Spotify (HTTP {e.http_status}) : {e.msg}", ephemeral=True)
            return
        except Exception as e:
            log.error(f"`/spy` Erreur inattendue | {type(e).__name__}: {e}")
            await interaction.followup.send("❌ Une erreur inattendue est survenue.", ephemeral=True)
            return

        uid  = interaction.user.id
        gid  = interaction.guild_id
        aid  = artist["id"]
        name = artist["name"]

        # Déjà abonné
        guild_data = tracked.get(str(gid), {})
        if aid in guild_data and uid in guild_data[aid].get("subscribers", []):
            await interaction.followup.send(f"⚠️ Tu es déjà abonné(e) à **{name}**.", ephemeral=True)
            return

        try:
            release = await get_latest_release(aid)
        except Exception as e:
            log.warning(f"`/spy` Impossible de récupérer la dernière sortie de '{name}' | {e}")
            release = None

        created = add_artist(gid, artist, release, notify_role=False, user_id=uid)
        action  = "ajouté et tu es abonné(e)" if created else "tu es maintenant abonné(e)"
        log.info(f"[Guild {gid}] {'Artiste ajouté' if created else 'Abonné ajouté'} : {interaction.user} → {name}")
        await interaction.followup.send(f"✅ **{name}** — {action} aux alertes !", ephemeral=True)

    # ── /unfollow ──────────────────────────────────────────────────────
    @app_commands.command(name="unspy", description="Se désabonner des alertes d'un artiste")
    @app_commands.describe(artiste="Nom de l'artiste")
    @app_commands.autocomplete(artiste=subscribed_autocomplete)
    async def unfollow(self, interaction: discord.Interaction, artiste: str):
        uid        = interaction.user.id
        gid        = interaction.guild_id
        guild_data = tracked.get(str(gid), {})

        match = next((aid for aid, info in guild_data.items()
                      if info["name"].lower() == artiste.lower()), None)
        if not match:
            await interaction.response.send_message(f"❌ **{artiste}** n'est pas dans la liste.", ephemeral=True)
            return

        info = guild_data[match]
        subs = info.get("subscribers", [])

        if uid not in subs:
            await interaction.response.send_message(
                f"⚠️ Tu n'es pas abonné(e) à **{info['name']}**.", ephemeral=True
            )
            return

        subs.remove(uid)
        save_data(tracked)
        log.info(f"[Guild {gid}] Abonné retiré : {interaction.user} → {info['name']}")
        cleanup_artist(gid, match)

        await interaction.response.send_message(f"✅ Tu es désabonné(e) de **{info['name']}**.", ephemeral=True)

    # ── /list ──────────────────────────────────────────────────────────
    @app_commands.command(name="liste", description="Voir les artistes suivis sur ce serveur")
    async def list_artists(self, interaction: discord.Interaction):
        guild_data = tracked.get(str(interaction.guild_id), {})
        if not guild_data:
            await interaction.response.send_message("📭 Aucun artiste suivi sur ce serveur.", ephemeral=True)
            return

        uid   = interaction.user.id
        lines = [
            f"{'🔔' if uid in info.get('subscribers', []) else '•'} **{info['name']}**"
            for info in guild_data.values()
        ]
        embed = discord.Embed(title="🎧 Artistes suivis", description="\n".join(lines), color=0x1DB954)
        embed.set_footer(text="🔔 = tu es abonné(e)")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /latest ────────────────────────────────────────────────────────
    @app_commands.command(name="derniere_sortie", description="Afficher la dernière sortie connue d'un artiste suivi")
    @app_commands.describe(artiste="Nom de l'artiste")
    @app_commands.autocomplete(artiste=artist_autocomplete)
    async def latest(self, interaction: discord.Interaction, artiste: str):
        guild_data = tracked.get(str(interaction.guild_id), {})
        match = next(((aid, info) for aid, info in guild_data.items()
                      if info["name"].lower() == artiste.lower()), None)

        if not match:
            await interaction.response.send_message(
                f"❌ **{artiste}** n'est pas dans la liste. Utilise `/liste` pour voir les artistes suivis.",
                ephemeral=True
            )
            return

        aid, info = match
        url  = info.get("last_release_url")
        name = info.get("last_release_name")

        if not url:
            await interaction.response.send_message(
                f"😕 Aucune sortie connue pour **{info['name']}** pour l'instant.", ephemeral=True
            )
            return

        await interaction.response.send_message(f"[{info['name']} — {name}]({url})")


async def setup(bot: commands.Bot):
    await bot.add_cog(SpotifyCog(bot))
    log.info("Cog SpotifyCog chargé")