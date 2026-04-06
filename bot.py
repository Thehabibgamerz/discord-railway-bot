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

# Import views SAFELY (prevents crash)
try:
    from cogs.tickets import TicketPanel, TicketControls, TicketCloseControls
    TICKETS_AVAILABLE = True
except:
    TICKETS_AVAILABLE = False
    print("⚠️ Ticket views not loaded (check class names in tickets.py)")

# Self roles
try:
    from cogs.selfroles import SelfRoleView
    SELFROLE_AVAILABLE = True
except:
    SELFROLE_AVAILABLE = False
    print("⚠️ SelfRoleView not found")

# Embed builder
try:
    from cogs.embed_builder_ui import EmbedView
    EMBED_AVAILABLE = True
except:
    EMBED_AVAILABLE = False
    print("⚠️ EmbedView not found")


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

    # 🎫 Ticket system (only if valid)
    if TICKETS_AVAILABLE:
        try:
            bot.add_view(TicketPanel())  
            bot.add_view(TicketControls())  
            bot.add_view(TicketCloseControls())  
            print("🎫 Ticket system ready")
        except Exception as e:
            print(f"❌ Ticket view error: {e}")

    # 🎭 Self roles (24x7)
    if SELFROLE_AVAILABLE:
        try:
            bot.add_view(SelfRoleView())
            print("🎭 Self roles ready (24x7)")
        except Exception as e:
            print(f"❌ Self role error: {e}")

    # 🧩 Embed builder
    if EMBED_AVAILABLE:
        try:
            bot.add_view(EmbedView(None))
            print("🧩 Embed builder ready")
        except Exception as e:
            print(f"❌ Embed view error: {e}")

    # 🌍 Sync commands
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
