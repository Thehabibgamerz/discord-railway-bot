import discord
from discord.ext import commands
from discord import app_commands
from supabase import create_client, Client
import os

STAFF_ROLE_ID = 1389824693388837035
SUPABASE_URL = "https://xljanwcgesjhdoaavmuo.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


def get_db() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def is_staff(member: discord.Member) -> bool:
    return any(role.id == STAFF_ROLE_ID for role in member.roles)


# ================= SUPABASE HELPERS =================

def db_get(guild_id: int):
    try:
        res = get_db().table("counting").select("*").eq("guild_id", guild_id).single().execute()
        return res.data
    except Exception:
        return None


def db_setup(guild_id: int, channel_id: int):
    db = get_db()
    existing = db_get(guild_id)
    if existing:
        db.table("counting").update({
            "channel_id": channel_id,
            "count": 0,
            "last_user_id": None
        }).eq("guild_id", guild_id).execute()
    else:
        db.table("counting").insert({
            "guild_id": guild_id,
            "channel_id": channel_id,
            "count": 0,
            "last_user_id": None
        }).execute()


def db_update(guild_id: int, count: int, last_user_id):
    get_db().table("counting").update({
        "count": count,
        "last_user_id": last_user_id
    }).eq("guild_id", guild_id).execute()


def db_reset(guild_id: int):
    get_db().table("counting").update({
        "count": 0,
        "last_user_id": None
    }).eq("guild_id", guild_id).execute()


# ================= COG =================

class Counting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ================= SETUP =================

    @app_commands.command(name="counting_setup", description="Set up the counting game channel (staff only)")
    @app_commands.describe(channel="The channel to use for counting")
    async def counting_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff can set up the counting game.", ephemeral=True
            )

        db_setup(interaction.guild.id, channel.id)

        embed = discord.Embed(
            title="🔢 Counting Game Set Up!",
            description=(
                f"Counting channel set to {channel.mention}.\n\n"
                "**Rules:**\n"
                "• Start from **1** and count up one number at a time.\n"
                "• You **cannot** count twice in a row — wait for someone else.\n"
                "• Send the wrong number and the count resets to 0.\n"
                "• ✅ = correct · ❌ = wrong (count resets)"
            ),
            color=discord.Color.orange()
        )
        embed.set_footer(text="AkasaAirVirtual • Counting Game")

        await interaction.response.send_message(embed=embed)
        await channel.send("🔢 **Counting game started!** Type **1** to begin.")

    # ================= RESET =================

    @app_commands.command(name="counting_reset", description="Manually reset the counting game (staff only)")
    async def counting_reset(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff can reset the counting game.", ephemeral=True
            )

        info = db_get(interaction.guild.id)
        if not info:
            return await interaction.response.send_message(
                "⚠️ Counting game is not set up. Use `/counting_setup` first.", ephemeral=True
            )

        db_reset(interaction.guild.id)

        channel = self.bot.get_channel(info["channel_id"])
        if channel:
            await channel.send("🔄 The counting game has been **reset** by staff. Type **1** to begin again!")

        await interaction.response.send_message("✅ Counting game reset.", ephemeral=True)

    # ================= MESSAGE LISTENER =================

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not message.guild:
            return

        # Fetch state from Supabase on every message in the right channel
        info = db_get(message.guild.id)
        if not info:
            return

        if message.channel.id != info["channel_id"]:
            return

        # Ignore non-numeric messages silently
        content = message.content.strip()
        if not content.lstrip("-").isdigit():
            return

        count = info["count"]
        last_user_id = info["last_user_id"]
        expected = count + 1
        sent = int(content)

        # Wrong number — reset
        if sent != expected:
            await message.add_reaction("❌")
            db_reset(message.guild.id)
            await message.channel.send(
                f"❌ {message.author.mention} ruined it at **{count}**! "
                f"The number should have been **{expected}**. "
                f"Starting over from **1**."
            )
            return

        # Same user counting twice in a row — warn only, no reset
        if last_user_id and int(last_user_id) == message.author.id:
            await message.add_reaction("⚠️")
            await message.channel.send(
                f"⚠️ {message.author.mention} you cannot count twice in a row! "
                f"Wait for someone else. The count is still at **{count}**.",
                delete_after=5
            )
            await message.delete()
            return

        # Correct number
        db_update(message.guild.id, sent, message.author.id)
        await message.add_reaction("✅")

        # Milestone every 100
        if sent % 100 == 0:
            await message.channel.send(
                f"🎉 **{sent}!** Amazing work everyone — keep it going!"
            )


async def setup(bot):
    await bot.add_cog(Counting(bot))
