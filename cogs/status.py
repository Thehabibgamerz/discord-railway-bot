import discord
from discord.ext import commands
from discord import app_commands

class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="status", description="Change bot status")
    @app_commands.describe(
        type="Type of status",
        text="Status message"
    )
    async def status(self, interaction: discord.Interaction, type: str, text: str):

        if type.lower() == "playing":
            activity = discord.Game(name=text)

        elif type.lower() == "watching":
            activity = discord.Activity(
                type=discord.ActivityType.watching,
                name=text
            )

        elif type.lower() == "listening":
            activity = discord.Activity(
                type=discord.ActivityType.listening,
                name=text
            )

        else:
            await interaction.response.send_message(
                "❌ Use: playing / watching / listening",
                ephemeral=True
            )
            return

        await self.bot.change_presence(activity=activity)

        await interaction.response.send_message(
            f"✅ Status changed to **{type} {text}**"
        )

async def setup(bot):
    await bot.add_cog(Status(bot))
