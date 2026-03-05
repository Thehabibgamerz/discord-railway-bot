import discord
from discord.ext import commands
from discord import app_commands
import datetime

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check latency")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("🏓 Pong!")

    @app_commands.command(name="avatar", description="Show user avatar")
    async def avatar(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        await interaction.response.send_message(user.avatar.url)

    @app_commands.command(name="userinfo", description="User info")
    async def userinfo(self, interaction: discord.Interaction, user: discord.Member = None):
        user = user or interaction.user
        embed = discord.Embed(title=user.name)
        embed.add_field(name="ID", value=user.id)
        embed.add_field(name="Joined", value=user.joined_at.date())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Server info")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(title=guild.name)
        embed.add_field(name="Members", value=guild.member_count)
        embed.add_field(name="Created", value=guild.created_at.date())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="time", description="Current UTC time")
    async def time(self, interaction: discord.Interaction):
        await interaction.response.send_message(str(datetime.datetime.utcnow()))

async def setup(bot):
    await bot.add_cog(Utility(bot))
