import discord
from discord import ui

from bot.data.storage import tracked
from bot.ui.list_buttons import SubscribeButton, UnsubscribeButton


def build_my_follows(user: discord.User | discord.Member, guild: discord.Guild) -> list:
    """Construit les composants pour la page 'Mes follows'."""
    gid = str(guild.id)
    uid = user.id
    guild_data = tracked.get(gid, {})

    components = []
    components.append(ui.TextDisplay("## 🔔 Mes follows"))
    components.append(ui.Separator(visible=True))

    followed = [
        (aid, info) for aid, info in guild_data.items()
        if uid in info.get("subscribers", [])
    ]

    if not followed:
        components.append(ui.TextDisplay("*Tu ne suis aucun artiste pour le moment.*"))
        return components

    for aid, info in followed:
        name = info["name"]
        last = info.get("last_release_name")
        text = f"**{name}**"
        if last:
            text += f"\n-# Dernière sortie : {last}"

        section = ui.Section(
            ui.TextDisplay(text),
            accessory=UnsubscribeButton(artist_id=aid, artist_name=name),
        )
        components.append(section)

    return components


def build_server_artists(user: discord.User | discord.Member, guild: discord.Guild) -> list:
    """Construit les composants pour la page 'Artistes du serveur' (non suivis)."""
    gid = str(guild.id)
    uid = user.id
    guild_data = tracked.get(gid, {})

    components = []
    components.append(ui.TextDisplay("## 📋 Artistes du serveur"))
    components.append(ui.Separator(visible=True))

    not_followed = [
        (aid, info) for aid, info in guild_data.items()
        if uid not in info.get("subscribers", [])
    ]

    if not not_followed:
        components.append(ui.TextDisplay("*Tu suis déjà tous les artistes du serveur !*"))
        return components

    for aid, info in not_followed:
        name = info["name"]
        last = info.get("last_release_name")
        text = f"**{name}**"
        if last:
            text += f"\n-# Dernière sortie : {last}"

        section = ui.Section(
            ui.TextDisplay(text),
            accessory=SubscribeButton(artist_id=aid, artist_name=name),
        )
        components.append(section)

    return components


def build_confirm_unsub(artist_name: str) -> list:
    """Construit les composants pour la confirmation de désabonnement."""
    return [
        ui.TextDisplay(f"## ⚠️ Confirmation"),
        ui.Separator(visible=True),
        ui.TextDisplay(f"Tu veux vraiment te désabonner de **{artist_name}** ?"),
    ]