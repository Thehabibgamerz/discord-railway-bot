import discord
from discord.ext import commands
from discord import app_commands
import json
import os

STAFF_ROLE_ID = 1389824693388837035

DATA_FILE = os.path.join(os.path.dirname(__file__), "counting.json")


# ================= PERSISTENCE =================

def load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_data(data: dict):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass


def is_staff(member: discord.Member) -> bool:
    return any(role.id == STAFF_ROLE_ID for role in member.roles)


# ================= COG =================

class Counting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # In-memory state: {guild_id: {channel_id, count, last_user_id}}
        self.state: dict = {}
        self._load_all()

    def _load_all(self):
        data = load_data()
        for guild_id, info in data.items():
            self.state[int(guild_id)] = {
                "channel_id": info.get("channel_id"),
                "count": info.get("count", 0),
                "last_user_id": info.get("last_user_id")
            }

    def _save_all(self):
        save_data({
            str(gid): {
                "channel_id": info["channel_id"],
                "count": info["count"],
                "last_user_id": info["last_user_id"]
            }
            for gid, info in self.state.items()
        })

    # ================= SETUP COMMAND =================

    @app_commands.command(name="counting_setup", description="Set up the counting game channel (staff only)")
    @app_commands.describe(channel="The channel to use for counting")
    async def counting_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff can set up the counting game.", ephemeral=True
            )

        self.state[interaction.guild.id] = {
            "channel_id": channel.id,
            "count": 0,
            "last_user_id": None
        }
        self._save_all()

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
        await channel.send(
            "🔢 **Counting game started!** Type **1** to begin."
        )

    # ================= RESET COMMAND =================

    @app_commands.command(name="counting_reset", description="Manually reset the counting game (staff only)")
    async def counting_reset(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff can reset the counting game.", ephemeral=True
            )

        info = self.state.get(interaction.guild.id)
        if not info:
            return await interaction.response.send_message(
                "⚠️ Counting game is not set up. Use `/counting_setup` first.", ephemeral=True
            )

        info["count"] = 0
        info["last_user_id"] = None
        self._save_all()

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

        info = self.state.get(message.guild.id)
        if not info:
            return

        if message.channel.id != info["channel_id"]:
            return

        # Ignore non-numeric messages silently
        content = message.content.strip()
        if not content.lstrip("-").isdigit():
            return

        expected = info["count"] + 1
        sent = int(content)

        # Wrong number
        if sent != expected:
            await message.add_reaction("❌")
            info["count"] = 0
            info["last_user_id"] = None
            self._save_all()
            await message.channel.send(
                f"❌ {message.author.mention} ruined it at **{info['count'] + sent - sent}**! "
                f"The number should have been **{expected}**. "
                f"Starting over from **1**."
            )
            return

        # Same user counting twice in a row — warn only, no reset
        if info["last_user_id"] == message.author.id:
            await message.add_reaction("⚠️")
            await message.channel.send(
                f"⚠️ {message.author.mention} you can't count twice in a row! "
                f"Wait for someone else. The count is still at **{info['count']}**.",
                delete_after=5
            )
            await message.delete()
            return

        # Correct number
        info["count"] = sent
        info["last_user_id"] = message.author.id
        self._save_all()
        await message.add_reaction("✅")

        # Milestone messages every 100
        if sent % 100 == 0:
            await message.channel.send(
                f"🎉 **{sent}!** Amazing work everyone — keep it going!"
            )


async def setup(bot):
    await bot.add_cog(Counting(bot))
