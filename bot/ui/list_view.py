import discord
from discord import ui

from bot.ui.list_builder import (
    build_my_follows,
    build_server_artists,
    build_confirm_unsub,
)
from bot.ui.list_buttons import (
    SwitchPageButton,
    PrevPageButton,
    NextPageButton,
    PageCounterButton,
    ConfirmYesButton,
    ConfirmNoButton,
)


class ArtistListView(ui.LayoutView):
    """Vue principale avec pagination : follows / server."""

    def __init__(self, user: discord.Member, page: str, page_index: int, items: list, total_pages: int):
        super().__init__(timeout=120)
        self.user = user
        self.page = page
        self.page_index = max(0, min(page_index, total_pages - 1))

        # ── Container principal ────────────────────────────────────────
        container = ui.Container(*items, accent_color=0x1DB954)
        self.add_item(container)

        # ── Ligne 1 : pagination ◀ X/Y ▶ (uniquement si > 1 page) ─────
        if total_pages > 1:
            prev_btn    = PrevPageButton(current_page_index=self.page_index, disabled=(self.page_index <= 0))
            counter_btn = PageCounterButton(current=self.page_index + 1, total=total_pages)
            next_btn    = NextPageButton(current_page_index=self.page_index, disabled=(self.page_index >= total_pages - 1))
            self.add_item(ui.ActionRow(prev_btn, counter_btn, next_btn))

        # ── Ligne 2 : onglets follows / serveur ────────────────────────
        nav_follows = SwitchPageButton(target_page="follows", disabled=(page == "follows"))
        nav_server  = SwitchPageButton(target_page="server",  disabled=(page == "server"))
        self.add_item(ui.ActionRow(nav_follows, nav_server))

    @classmethod
    async def create(cls, user: discord.Member, guild: discord.Guild, page: str = "follows", page_index: int = 0):
        """Factory async — charge les données puis construit la vue."""
        if page == "server":
            items, total_pages = await build_server_artists(user, guild, page_index)
        else:
            items, total_pages = await build_my_follows(user, guild, page_index)
            page = "follows"

        return cls(user, page, page_index, items, total_pages)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "🚫 Cette interface ne t'appartient pas.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        self.stop()


class ConfirmUnsubView(ui.LayoutView):
    """Confirmation de désabonnement utilisateur."""

    def __init__(
        self,
        user: discord.Member,
        guild: discord.Guild,
        artist_id: str,
        artist_name: str,
        parent_page: str,
        parent_page_index: int = 0,
    ):
        super().__init__(timeout=30)
        self.user = user
        self.guild = guild
        self.artist_id = artist_id
        self.artist_name = artist_name
        self.parent_page = parent_page
        self.parent_page_index = parent_page_index

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
        self.stop()