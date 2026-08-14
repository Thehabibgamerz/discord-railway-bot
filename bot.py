import discord
from discord.ext import commands
import os
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# ================= SAFE VIEW IMPORTS =================

try:
    from cogs.tickets import TicketPanel, TicketControls, TicketCloseControls
    TICKETS_AVAILABLE = True
except Exception as e:
    TICKETS_AVAILABLE = False
    print(f"⚠️ Ticket views not loaded: {e}")

try:
    from cogs.selfroles import SelfRoleView
    SELFROLE_AVAILABLE = True
except Exception as e:
    SELFROLE_AVAILABLE = False
    print(f"⚠️ SelfRoleView not found: {e}")

# ================= LOAD COGS =================

async def load_cogs():
    for file in os.listdir("./cogs"):
        if file.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{file[:-3]}")
                print(f"✅ Loaded cog: {file}")
            except Exception as e:
                print(f"❌ Failed to load {file}: {e}")

# ================= READY EVENT =================

@bot.event
async def on_ready():
    print(f"🤖 Bot logged in as {bot.user}")

    # 🎫 Ticket system
    if TICKETS_AVAILABLE:
        try:
            bot.add_view(TicketPanel())
            bot.add_view(TicketControls())
            bot.add_view(TicketCloseControls())
            print("🎫 Ticket system ready")
        except Exception as e:
            print(f"❌ Ticket view error: {e}")

    # 🎭 Self roles
    if SELFROLE_AVAILABLE:
        try:
            bot.add_view(SelfRoleView())
            print("🎭 Self roles ready")
        except Exception as e:
            print(f"❌ Self role error: {e}")

    # 🌍 Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"🌐 Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Slash sync failed: {e}")

# ================= START BOT =================

async def main():
    async with bot:
        await load_cogs()
        await bot.start(os.getenv("TOKEN"))

asyncio.run(main())
