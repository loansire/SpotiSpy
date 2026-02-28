import discord
from discord import ui

from bot.data.storage import tracked, save_data, cleanup_artist
from bot.utils.logger import log


# ── Boutons utilisateur ────────────────────────────────────────────────


class SubscribeButton(ui.Button):
    """Bouton 🔔 pour s'abonner à un artiste."""

    def __init__(self, artist_id: str, artist_name: str):
        super().__init__(
            emoji="🔔",
            style=discord.ButtonStyle.success,
            custom_id=f"sub:{artist_id}",
        )
        self.artist_id = artist_id
        self.artist_name = artist_name

    async def callback(self, interaction: discord.Interaction):
        uid = interaction.user.id
        gid = str(interaction.guild_id)
        guild_data = tracked.get(gid, {})
        info = guild_data.get(self.artist_id)

        if not info:
            await interaction.response.send_message(
                f"❌ **{self.artist_name}** n'existe plus dans la liste.", ephemeral=True
            )
            return

        subs = info.setdefault("subscribers", [])
        if uid in subs:
            await interaction.response.send_message(
                f"⚠️ Tu es déjà abonné(e) à **{self.artist_name}**.", ephemeral=True
            )
            return

        subs.append(uid)
        save_data(tracked)
        log.info(f"[Guild {gid}] Abonné ajouté via UI : {interaction.user} → {self.artist_name}")

        from bot.ui.list_view import ArtistListView
        view = ArtistListView(interaction.user, interaction.guild, page=self.view.page, page_index=self.view.page_index)
        await interaction.response.edit_message(view=view)


class UnsubscribeButton(ui.Button):
    """Bouton ❌ pour se désabonner (ouvre la confirmation)."""

    def __init__(self, artist_id: str, artist_name: str):
        super().__init__(
            emoji="❌",
            style=discord.ButtonStyle.secondary,
            custom_id=f"unsub:{artist_id}",
        )
        self.artist_id = artist_id
        self.artist_name = artist_name

    async def callback(self, interaction: discord.Interaction):
        from bot.ui.list_view import ConfirmUnsubView
        view = ConfirmUnsubView(
            user=interaction.user,
            guild=interaction.guild,
            artist_id=self.artist_id,
            artist_name=self.artist_name,
            parent_page=self.view.page,
            parent_page_index=self.view.page_index,
        )
        await interaction.response.edit_message(view=view)


class ConfirmYesButton(ui.Button):
    """Confirme le désabonnement."""

    def __init__(self):
        super().__init__(label="Confirmer", emoji="✅", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        view: "ConfirmUnsubView" = self.view
        uid = interaction.user.id
        gid = str(interaction.guild_id)
        guild_data = tracked.get(gid, {})
        info = guild_data.get(view.artist_id)

        if info:
            subs = info.get("subscribers", [])
            if uid in subs:
                subs.remove(uid)
                save_data(tracked)
                log.info(f"[Guild {gid}] Abonné retiré via UI : {interaction.user} → {view.artist_name}")
                cleanup_artist(int(gid), view.artist_id)

        from bot.ui.list_view import ArtistListView
        new_view = ArtistListView(interaction.user, interaction.guild, page=view.parent_page, page_index=view.parent_page_index)
        await interaction.response.edit_message(view=new_view)


class ConfirmNoButton(ui.Button):
    """Annule le désabonnement."""

    def __init__(self):
        super().__init__(label="Annuler", emoji="↩️", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: "ConfirmUnsubView" = self.view
        from bot.ui.list_view import ArtistListView
        new_view = ArtistListView(interaction.user, interaction.guild, page=view.parent_page, page_index=view.parent_page_index)
        await interaction.response.edit_message(view=new_view)


# ── Boutons navigation de page (onglets) ───────────────────────────────


class SwitchPageButton(ui.Button):
    """Bouton pour changer de page (onglet)."""

    def __init__(self, target_page: str, disabled: bool = False):
        labels = {
            "server":  ("📋", "Serveur"),
            "follows": ("🔔", "Mes follows"),
        }
        emoji, label = labels.get(target_page, ("❓", target_page))
        super().__init__(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.primary,
            disabled=disabled,
        )
        self.target_page = target_page

    async def callback(self, interaction: discord.Interaction):
        from bot.ui.list_view import ArtistListView
        # Changement d'onglet → retour à la page 0
        view = ArtistListView(interaction.user, interaction.guild, page=self.target_page, page_index=0)
        await interaction.response.edit_message(view=view)


# ── Boutons de pagination (flèches) ────────────────────────────────────


class PrevPageButton(ui.Button):
    """Bouton ◀ pour aller à la page précédente."""

    def __init__(self, current_page_index: int, disabled: bool = False):
        super().__init__(
            emoji="◀",
            style=discord.ButtonStyle.secondary,
            disabled=disabled,
        )
        self.current_page_index = current_page_index

    async def callback(self, interaction: discord.Interaction):
        from bot.ui.list_view import ArtistListView
        view = ArtistListView(
            interaction.user,
            interaction.guild,
            page=self.view.page,
            page_index=self.current_page_index - 1,
        )
        await interaction.response.edit_message(view=view)


class NextPageButton(ui.Button):
    """Bouton ▶ pour aller à la page suivante."""

    def __init__(self, current_page_index: int, disabled: bool = False):
        super().__init__(
            emoji="▶",
            style=discord.ButtonStyle.secondary,
            disabled=disabled,
        )
        self.current_page_index = current_page_index

    async def callback(self, interaction: discord.Interaction):
        from bot.ui.list_view import ArtistListView
        view = ArtistListView(
            interaction.user,
            interaction.guild,
            page=self.view.page,
            page_index=self.current_page_index + 1,
        )
        await interaction.response.edit_message(view=view)


class PageCounterButton(ui.Button):
    """Bouton désactivé affichant X/Y au centre."""

    def __init__(self, current: int, total: int):
        super().__init__(
            label=f"{current}/{total}",
            style=discord.ButtonStyle.secondary,
            disabled=True,
        )