import discord
from discord.ext import commands
from discord import app_commands

class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="status",
        description="Set the bot's status (Playing, Watching, Listening, Competing)"
    )
    @app_commands.describe(
        activity="Type of activity", 
        text="Text to display in the status"
    )
    @app_commands.choices(activity=[
        app_commands.Choice(name="Playing", value="playing"),
        app_commands.Choice(name="Watching", value="watching"),
        app_commands.Choice(name="Listening", value="listening"),
        app_commands.Choice(name="Competing", value="competing")
    ])
    async def status(self, interaction: discord.Interaction, activity: app_commands.Choice[str], text: str):
        """Set the bot presence"""
        activity_type = activity.value

        if activity_type == "playing":
            await self.bot.change_presence(activity=discord.Game(name=text))
        elif activity_type == "watching":
            await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=text))
        elif activity_type == "listening":
            await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=text))
        elif activity_type == "competing":
            await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.competing, name=text))

        await interaction.response.send_message(f"✅ Status updated: **{activity.name} {text}**", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Status(bot))
