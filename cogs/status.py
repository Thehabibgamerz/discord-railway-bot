import discord
from discord.ext import commands
from discord import app_commands
import json
import os

STAFF_ROLE_ID = 1389824693388837035

STATUS_FILE = os.path.join(os.path.dirname(__file__), "bot_status.json")


# ================= PERSISTENCE =================

def load_status():
    if not os.path.exists(STATUS_FILE):
        return None
    try:
        with open(STATUS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return None


def save_status(data: dict):
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass


def is_staff(member: discord.Member) -> bool:
    return any(role.id == STAFF_ROLE_ID for role in member.roles)


async def apply_status(bot: commands.Bot, activity_type: str, text: str, status_type: str):
    """Applies the activity and status to the bot."""

    match activity_type:
        case "playing":
            activity = discord.Game(name=text)
        case "watching":
            activity = discord.Activity(type=discord.ActivityType.watching, name=text)
        case "listening":
            activity = discord.Activity(type=discord.ActivityType.listening, name=text)
        case "competing":
            activity = discord.Activity(type=discord.ActivityType.competing, name=text)
        case _:
            activity = None

    match status_type:
        case "online":
            status = discord.Status.online
        case "idle":
            status = discord.Status.idle
        case "dnd":
            status = discord.Status.dnd
        case _:
            status = discord.Status.online

    await bot.change_presence(status=status, activity=activity)


# ================= COG =================

class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Restore saved status every time the bot connects or reconnects
    @commands.Cog.listener()
    async def on_ready(self):
        saved = load_status()
        if saved:
            await apply_status(
                self.bot,
                saved.get("activity_type", "playing"),
                saved.get("text", "Akasa Air Virtual"),
                saved.get("status_type", "online")
            )

    # ================= SET STATUS =================

    @app_commands.command(
        name="setstatus",
        description="Set the bot activity and online status (staff only)"
    )
    @app_commands.describe(
        activity="Type of activity",
        text="Text to display in the status",
        status="Bot online status (online, idle, dnd)"
    )
    @app_commands.choices(
        activity=[
            app_commands.Choice(name="Playing", value="playing"),
            app_commands.Choice(name="Watching", value="watching"),
            app_commands.Choice(name="Listening", value="listening"),
            app_commands.Choice(name="Competing", value="competing")
        ],
        status=[
            app_commands.Choice(name="Online", value="online"),
            app_commands.Choice(name="Idle", value="idle"),
            app_commands.Choice(name="Do Not Disturb", value="dnd")
        ]
    )
    async def setstatus(
        self,
        interaction: discord.Interaction,
        activity: app_commands.Choice[str],
        text: str,
        status: app_commands.Choice[str] = None
    ):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff members can change the bot status.", ephemeral=True
            )

        status_type = status.value if status else "online"
        status_name = status.name if status else "Online"

        await apply_status(self.bot, activity.value, text, status_type)

        save_status({
            "activity_type": activity.value,
            "text": text,
            "status_type": status_type
        })

        await interaction.response.send_message(
            f"✅ Status updated!\n"
            f"**Activity:** {activity.name} {text}\n"
            f"**Status:** {status_name}",
            ephemeral=True
        )

    # ================= CLEAR STATUS =================

    @app_commands.command(
        name="clearstatus",
        description="Clear the bot's activity status (staff only)"
    )
    async def clearstatus(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff members can change the bot status.", ephemeral=True
            )

        await self.bot.change_presence(status=discord.Status.online, activity=None)

        save_status({
            "activity_type": None,
            "text": None,
            "status_type": "online"
        })

        await interaction.response.send_message(
            "✅ Bot status cleared.", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Status(bot))
