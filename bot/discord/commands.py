import discord
from discord import app_commands
from discord.ext import commands
from spotipy.exceptions import SpotifyException

from bot.data.storage import tracked, save_data
from bot.spotify.api import get_artist_from_url, get_latest_release
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

    # ── /follow ────────────────────────────────────────────────────────
    @app_commands.command(name="follow", description="S'abonner aux alertes d'un artiste Spotify")
    @app_commands.describe(url="Lien de la page Spotify de l'artiste (ex: https://open.spotify.com/artist/...)")
    async def follow(self, interaction: discord.Interaction, url: str):
        await interaction.response.defer(ephemeral=True)
        uid = interaction.user.id

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
            log.error(f"/follow SpotifyException | HTTP {e.http_status} | {e.msg}")
            await interaction.followup.send(f"❌ Erreur Spotify (HTTP {e.http_status}) : {e.msg}", ephemeral=True)
            return
        except Exception as e:
            log.error(f"/follow Erreur inattendue | {type(e).__name__}: {e}")
            await interaction.followup.send("❌ Une erreur inattendue est survenue. Merci de signaler le problème à un administrateur.", ephemeral=True)
            return

        aid  = artist["id"]
        name = artist["name"]

        # Artiste déjà en base → ajouter l'utilisateur aux abonnés
        if aid in tracked:
            subs = tracked[aid].setdefault("subscribers", [])
            if uid in subs:
                await interaction.followup.send(f"⚠️ Tu es déjà abonné(e) à **{name}**.", ephemeral=True)
                return
            subs.append(uid)
            save_data(tracked)
            log.info(f"Abonné ajouté : {interaction.user} → {name}")
            await interaction.followup.send(f"✅ Tu es maintenant abonné(e) à **{name}** !", ephemeral=True)
            return

        # Nouvel artiste → créer l'entrée + abonner l'utilisateur
        try:
            release = await get_latest_release(aid)
        except Exception as e:
            log.warning(f"/follow Impossible de récupérer la dernière sortie de '{name}' | {e}")
            release = None

        tracked[aid] = {
            "name": name,
            "last_release_id":   release["id"] if release else None,
            "last_release_name": release["name"] if release else None,
            "last_release_url":  release["external_urls"]["spotify"] if release else None,
            "subscribers": [uid],
            "notify_role": False
        }
        save_data(tracked)
        log.info(f"Artiste ajouté : {name} ({aid}) — abonné : {interaction.user}")
        await interaction.followup.send(f"✅ **{name}** ajouté et tu es abonné(e) aux alertes !", ephemeral=True)

    # ── /unfollow ──────────────────────────────────────────────────────
    @app_commands.command(name="unfollow", description="Se désabonner des alertes d'un artiste")
    @app_commands.describe(artiste="Nom de l'artiste")
    @app_commands.autocomplete(artiste=artist_autocomplete)
    async def unfollow(self, interaction: discord.Interaction, artiste: str):
        uid = interaction.user.id

        match = next((aid for aid, info in tracked.items()
                      if info["name"].lower() == artiste.lower()), None)
        if not match:
            await interaction.response.send_message(f"❌ **{artiste}** n'est pas dans la liste.", ephemeral=True)
            return

        info = tracked[match]
        subs = info.get("subscribers", [])

        if uid not in subs:
            await interaction.response.send_message(f"⚠️ Tu n'es pas abonné(e) à **{info['name']}**.", ephemeral=True)
            return

        subs.remove(uid)

        # Supprimer l'artiste si plus aucun abonné ET pas de ping rôle admin
        if not subs and not info.get("notify_role"):
            del tracked[match]
            save_data(tracked)
            log.info(f"Artiste supprimé (plus d'abonnés) : {info['name']} ({match})")
            await interaction.response.send_message(f"🗑️ Tu es désabonné(e) de **{info['name']}** (artiste retiré de la liste).", ephemeral=True)
            return

        save_data(tracked)
        log.info(f"Abonné retiré : {interaction.user} → {info['name']}")
        await interaction.response.send_message(f"✅ Tu es désabonné(e) de **{info['name']}**.", ephemeral=True)

    # ── /list ──────────────────────────────────────────────────────────
    @app_commands.command(name="list", description="Voir les artistes suivis")
    async def list_artists(self, interaction: discord.Interaction):
        if not tracked:
            await interaction.response.send_message("📭 Aucun artiste suivi pour l'instant.", ephemeral=True)
            return

        uid = interaction.user.id
        lines = []
        for info in tracked.values():
            subscribed = uid in info.get("subscribers", [])
            marker = "🔔" if subscribed else "•"
            lines.append(f"{marker} **{info['name']}**")

        embed = discord.Embed(
            title="🎧 Artistes suivis",
            description="\n".join(lines),
            color=0x1DB954
        )
        embed.set_footer(text="🔔 = tu es abonné(e)")
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


# ─── SETUP ─────────────────────────────────────────────────────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(SpotifyCog(bot))
    log.info("Cog SpotifyCog chargé")