import discord
from discord.ext import commands
from discord import app_commands
import random

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="coinflip", description="Flip a coin")
    async def coinflip(self, interaction: discord.Interaction):
        await interaction.response.send_message(random.choice(["Heads", "Tails"]))

    @app_commands.command(name="dice", description="Roll a dice")
    async def dice(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🎲 {random.randint(1,6)}")

    @app_commands.command(name="8ball", description="Ask the magic 8ball")
    async def eightball(self, interaction: discord.Interaction, question: str):
        responses = ["Yes", "No", "Maybe", "Definitely", "Ask later"]
        await interaction.response.send_message(random.choice(responses))

    @app_commands.command(name="joke", description="Random joke")
    async def joke(self, interaction: discord.Interaction):
        jokes = [
            "Why did the computer get cold? It forgot to close Windows.",
            "Why do programmers prefer dark mode? Because light attracts bugs."
        ]
        await interaction.response.send_message(random.choice(jokes))

async def setup(bot):
    await bot.add_cog(Fun(bot))
