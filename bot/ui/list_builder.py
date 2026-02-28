import discord
from discord import ui

from bot.data.storage import tracked
from bot.ui.list_buttons import (
    SubscribeButton,
    UnsubscribeButton,
)

PAGE_SIZE = 4  # Artistes affichés par page


def _artist_text(info: dict) -> str:
    """Texte formaté pour un artiste."""
    text = f"**{info['name']}**"
    last = info.get("last_release_name")
    if last:
        text += f"\n-# Dernière sortie : {last}"
    return text


def _paginate(items: list, page_index: int) -> tuple[list, int]:
    """Retourne (slice de la page, nombre total de pages)."""
    total_pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page_index = max(0, min(page_index, total_pages - 1))
    start = page_index * PAGE_SIZE
    return items[start:start + PAGE_SIZE], total_pages


def build_my_follows(user: discord.Member, guild: discord.Guild, page_index: int = 0) -> tuple[list, int]:
    """Page 'Mes follows' — artistes auxquels l'utilisateur est abonné."""
    gid = str(guild.id)
    uid = user.id
    guild_data = tracked.get(gid, {})

    followed = [
        (aid, info) for aid, info in guild_data.items()
        if uid in info.get("subscribers", [])
    ]

    page_items, total_pages = _paginate(followed, page_index)

    components = []
    components.append(ui.TextDisplay("## 🔔 Mes follows"))
    components.append(ui.Separator(visible=True))

    if not followed:
        components.append(ui.TextDisplay("*Tu ne suis aucun artiste pour le moment.*"))
        return components, 1

    for i, (aid, info) in enumerate(page_items):
        if i > 0:
            components.append(ui.Separator(visible=True))
        img = info.get("image_url")
        text = ui.TextDisplay(_artist_text(info))
        if img:
            components.append(ui.Section(text, accessory=ui.Thumbnail(img)))
        else:
            components.append(text)
        components.append(ui.ActionRow(UnsubscribeButton(artist_id=aid, artist_name=info["name"])))

    return components, total_pages


def build_server_artists(user: discord.Member, guild: discord.Guild, page_index: int = 0) -> tuple[list, int]:
    """Page 'Artistes du serveur' — artistes non suivis par l'utilisateur."""
    gid = str(guild.id)
    uid = user.id
    guild_data = tracked.get(gid, {})

    not_followed = [
        (aid, info) for aid, info in guild_data.items()
        if uid not in info.get("subscribers", [])
    ]

    page_items, total_pages = _paginate(not_followed, page_index)

    components = []
    components.append(ui.TextDisplay("## 📋 Artistes du serveur"))
    components.append(ui.Separator(visible=True))

    if not not_followed:
        components.append(ui.TextDisplay("*Tu suis déjà tous les artistes du serveur !*"))
        return components, 1

    for i, (aid, info) in enumerate(page_items):
        if i > 0:
            components.append(ui.Separator(visible=True))
        img = info.get("image_url")
        text = ui.TextDisplay(_artist_text(info))
        if img:
            components.append(ui.Section(text, accessory=ui.Thumbnail(img)))
        else:
            components.append(text)
        components.append(ui.ActionRow(SubscribeButton(artist_id=aid, artist_name=info["name"])))

    return components, total_pages


def build_confirm_unsub(artist_name: str) -> list:
    """Confirmation de désabonnement."""
    return [
        ui.TextDisplay("## ⚠️ Confirmation"),
        ui.Separator(visible=True),
        ui.TextDisplay(f"Te désabonner de **{artist_name}** ?"),
    ]