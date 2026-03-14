import discord
from discord.ext import commands
import os
import asyncio

# Import ticket views for persistent buttons
from cogs.tickets import TicketPanel, TicketControls, TicketCloseControls

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# Load all cogs automatically
async def load_cogs():
    for file in os.listdir("./cogs"):
        if file.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{file[:-3]}")
                print(f"✅ Loaded cog: {file}")
            except Exception as e:
                print(f"❌ Failed to load {file}: {e}")


@bot.event
async def on_ready():

    print(f"🤖 Bot logged in as {bot.user}")

    # Register persistent ticket views (fixes interaction failed)
    bot.add_view(TicketPanel())
    bot.add_view(TicketControls())
    bot.add_view(TicketCloseControls())

    print("🎫 Ticket system ready (persistent views enabled)")

    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"🌐 Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Slash command sync failed: {e}")


async def main():
    async with bot:
        await load_cogs()
        await bot.start(os.getenv("TOKEN"))


asyncio.run(main())
