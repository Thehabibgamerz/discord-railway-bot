import discord
from discord.ext import commands
from discord import app_commands
import os

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Runs when bot starts
@bot.event
async def on_ready():
    await bot.tree.sync()  # sync slash commands
    print(f"Logged in as {bot.user}")

# Slash command: /ping
@bot.tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong!")

# Slash command: /hello
@bot.tree.command(name="hello", description="Say hello")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f"Hello {interaction.user.mention}! 👋")

TOKEN = os.getenv("TOKEN")

bot.run(TOKEN)
