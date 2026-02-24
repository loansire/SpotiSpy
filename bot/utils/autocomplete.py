import discord
from discord import app_commands
from bot.data.storage import tracked


async def artist_autocomplete(interaction: discord.Interaction, current: str):
    """Autocomplete tous les artistes du serveur."""
    guild_data = tracked.get(str(interaction.guild_id), {})
    return [
        app_commands.Choice(name=info["name"], value=info["name"])
        for info in guild_data.values()
        if current.lower() in info["name"].lower()
    ][:25]


async def subscribed_autocomplete(interaction: discord.Interaction, current: str):
    """Autocomplete uniquement les artistes auxquels l'utilisateur est abonné."""
    guild_data = tracked.get(str(interaction.guild_id), {})
    uid = interaction.user.id
    return [
        app_commands.Choice(name=info["name"], value=info["name"])
        for info in guild_data.values()
        if uid in info.get("subscribers", []) and current.lower() in info["name"].lower()
    ][:25]