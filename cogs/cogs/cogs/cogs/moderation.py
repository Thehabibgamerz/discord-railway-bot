import discord
from discord.ext import commands
from discord import app_commands

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="kick", description="Kick a member")
    async def kick(self, interaction: discord.Interaction, member: discord.Member):
        await member.kick()
        await interaction.response.send_message(f"{member} kicked.")

    @app_commands.command(name="ban", description="Ban a member")
    async def ban(self, interaction: discord.Interaction, member: discord.Member):
        await member.ban()
        await interaction.response.send_message(f"{member} banned.")

    @app_commands.command(name="clear", description="Clear messages")
    async def clear(self, interaction: discord.Interaction, amount: int):
        await interaction.channel.purge(limit=amount)
        await interaction.response.send_message("Messages cleared.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Moderation(bot))
