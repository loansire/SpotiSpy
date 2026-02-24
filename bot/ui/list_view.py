import discord
from discord import ui

from bot.ui.list_builder import build_my_follows, build_server_artists, build_confirm_unsub
from bot.ui.list_buttons import SwitchPageButton, ConfirmYesButton, ConfirmNoButton


class ArtistListView(ui.LayoutView):
    """Vue principale avec 2 pages : 'follows' et 'server'."""

    def __init__(self, user: discord.User | discord.Member, guild: discord.Guild, page: str = "follows"):
        super().__init__(timeout=120)
        self.user = user
        self.page = page

        # Construire le contenu selon la page
        if page == "follows":
            items = build_my_follows(user, guild)
            switch = SwitchPageButton(target_page="server")
        else:
            items = build_server_artists(user, guild)
            switch = SwitchPageButton(target_page="follows")

        # Container principal
        container = ui.Container(*items, accent_color=0x1DB954)
        self.add_item(container)

        # Bouton switch en bas (dans un ActionRow séparé)
        row = ui.ActionRow(switch)
        self.add_item(row)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "🚫 Cette interface ne t'appartient pas.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        # Désactiver tous les boutons après timeout
        for child in self.walk_children():
            if isinstance(child, ui.Button):
                child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class ConfirmUnsubView(ui.LayoutView):
    """Vue de confirmation de désabonnement."""

    def __init__(
        self,
        user: discord.User | discord.Member,
        guild: discord.Guild,
        artist_id: str,
        artist_name: str,
        parent_page: str,
    ):
        super().__init__(timeout=30)
        self.user = user
        self.artist_id = artist_id
        self.artist_name = artist_name
        self.parent_page = parent_page
        self.guild = guild

        items = build_confirm_unsub(artist_name)
        container = ui.Container(*items, accent_color=0xFF0000)
        self.add_item(container)

        row = ui.ActionRow(ConfirmYesButton(), ConfirmNoButton())
        self.add_item(row)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "🚫 Cette interface ne t'appartient pas.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        # Retour à la liste si timeout
        from bot.ui.list_view import ArtistListView
        view = ArtistListView(self.user, self.guild, page=self.parent_page)
        if self.message:
            try:
                await self.message.edit(view=view)
            except discord.HTTPException:
                pass