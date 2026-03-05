import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong! 🏓")

@bot.command()
async def hello(ctx):
    await ctx.send(f"Hello {ctx.author.mention} 👋")

TOKEN = os.getenv("TOKEN")

bot.run(TOKEN)
