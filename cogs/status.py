import discord
from discord.ext import commands
from discord import app_commands

class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="status",
        description="Set the bot's activity (Playing, Watching, Listening, Competing)"
    )
    @app_commands.describe(
        message="The status message to show",
    )
    async def status(self, interaction: discord.Interaction, message: str):
        """Slash command to set the bot status"""
        # Step 1: Create dropdown for activity type
        class ActivitySelect(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label="Playing", description="Set bot as Playing ..."),
                    discord.SelectOption(label="Watching", description="Set bot as Watching ..."),
                    discord.SelectOption(label="Listening", description="Set bot as Listening ..."),
                    discord.SelectOption(label="Competing", description="Set bot as Competing ...")
                ]
                super().__init__(placeholder="Select activity type...", min_values=1, max_values=1, options=options)

            async def callback(self, select_interaction: discord.Interaction):
                choice = self.values[0]

                if choice == "Playing":
                    await self.bot.change_presence(activity=discord.Game(name=message))
                elif choice == "Watching":
                    await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=message))
                elif choice == "Listening":
                    await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=message))
                elif choice == "Competing":
                    await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.competing, name=message))

                await select_interaction.response.send_message(
                    f"✅ Status updated: **{choice} {message}**", ephemeral=True
                )

        view = discord.ui.View()
        view.add_item(ActivitySelect())
        await interaction.response.send_message(
            "Select the activity type for the bot:", view=view, ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(Status(bot))
