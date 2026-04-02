import discord
from discord import app_commands
from discord.ext import commands
from spotipy.exceptions import SpotifyException

from bot.data import storage
from bot.data.pending import add_to_queue, is_duplicate
from bot.spotify.api import get_artist_from_url, get_latest_release
from bot.spotify.rate_limit import is_rate_limited, activate_rate_limit, extract_retry_after, format_remaining
from bot.ui.list_view import ArtistListView
from bot.utils.autocomplete import artist_autocomplete, subscribed_autocomplete
from bot.utils.logger import log

class SpotifyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /spy ───────────────────────────────────────────────────────────
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

        # ── Rate limit actif → mise en file d'attente ──────────────────
        if is_rate_limited():
            gid = interaction.guild_id
            uid = interaction.user.id

            if is_duplicate(gid, url):
                await interaction.followup.send(
                    "⚠️ Cette demande est déjà en file d'attente.",
                    ephemeral=True
                )
                return

            add_to_queue(gid, uid, url)
            await interaction.followup.send(
                f"⏳ L'API Spotify est temporairement indisponible. "
                f"Ta demande sera traitée automatiquement. "
                f"Temps restant estimé : **{format_remaining()}**.",
                ephemeral=True
            )
            return

        # ── Fonctionnement normal ──────────────────────────────────────
        try:
            artist = await get_artist_from_url(url, priority=True)
            if not artist:
                await interaction.followup.send("❌ Impossible de récupérer l'artiste.", ephemeral=True)
                return
        except SpotifyException as e:
            if e.http_status == 429:
                retry_after = extract_retry_after(e)
                activate_rate_limit(retry_after, self.bot)
                add_to_queue(interaction.guild_id, interaction.user.id, url)
                await interaction.followup.send(
                    f"⏳ L'API Spotify est temporairement indisponible. "
                    f"Ta demande sera traitée automatiquement. "
                    f"Temps restant estimé : **{format_remaining()}**.",
                    ephemeral=True
                )
                return
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

        # Déjà abonné ?
        if await storage.is_subscribed(gid, aid, uid):
            await interaction.followup.send(f"⚠️ Tu es déjà abonné(e) à **{name}**.", ephemeral=True)
            return

        # Récupérer la dernière sortie
        release = None
        try:
            release = await get_latest_release(aid, priority=True)
        except SpotifyException as e:
            if e.http_status == 429:
                retry_after = extract_retry_after(e)
                activate_rate_limit(retry_after, self.bot)
            log.warning(f"`/spy` Impossible de récupérer la dernière sortie de '{name}' | {e}")
        except Exception as e:
            log.warning(f"`/spy` Impossible de récupérer la dernière sortie de '{name}' | {e}")

        # Ajouter l'artiste + abonnement
        created = await storage.add_artist(gid, artist, release)
        await storage.add_subscriber(gid, aid, uid)

        action = "ajouté et tu es abonné(e)" if created else "tu es maintenant abonné(e)"
        log.info(f"[Guild {gid}] {'Artiste ajouté' if created else 'Abonné ajouté'} : {interaction.user} → {name}")
        await interaction.followup.send(f"✅ **{name}** — {action} aux alertes !", ephemeral=True)

    # ── /liste ─────────────────────────────────────────────────────────
    @app_commands.command(name="liste", description="Voir les artistes suivis sur ce serveur")
    async def list_artists(self, interaction: discord.Interaction):
        artists = await storage.get_guild_artists(interaction.guild_id)
        if not artists:
            await interaction.response.send_message("📭 Aucun artiste suivi sur ce serveur.", ephemeral=True)
            return

        view = await ArtistListView.create(interaction.user, interaction.guild, page="follows")
        await interaction.response.send_message(view=view, ephemeral=True)

    # ── /derniere_sortie ───────────────────────────────────────────────
    @app_commands.command(name="derniere_sortie", description="Afficher la dernière sortie connue d'un artiste suivi")
    @app_commands.describe(artiste="Nom de l'artiste")
    @app_commands.autocomplete(artiste=artist_autocomplete)
    async def latest(self, interaction: discord.Interaction, artiste: str):
        artists = await storage.get_guild_artists(interaction.guild_id)
        match = next((a for a in artists if a["name"].lower() == artiste.lower()), None)

        if not match:
            await interaction.response.send_message(
                f"❌ **{artiste}** n'est pas dans la liste. Utilise `/liste` pour voir les artistes suivis.",
                ephemeral=True
            )
            return

        url  = match.get("last_release_url")
        name = match.get("last_release_name")

        if not url:
            await interaction.response.send_message(
                f"😕 Aucune sortie connue pour **{match['name']}** pour l'instant.", ephemeral=True
            )
            return

        await interaction.response.send_message(f"[{match['name']} — {name}]({url})")


async def setup(bot: commands.Bot):
    await bot.add_cog(SpotifyCog(bot))
    log.info("Cog SpotifyCog chargé")