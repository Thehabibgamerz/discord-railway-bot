import discord
from discord.ext import commands
from discord import app_commands
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta
import os

STAFF_ROLE_ID = 1389824693388837035
EXEC_ROLE_ID = 1389824452778262589

SUPABASE_URL = "https://xljanwcgesjhdoaavmuo.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

INACTIVITY_DAYS = 30

INACTIVITY_MESSAGE = """## Akasa Air Virtual - Inactivity Check! ⌛

Hello Captain,

Our records indicate that you have **not filed a PIREP** within the last **30 days**.

According to Akasa Air Virtual policy, all pilots must file at least **1 PIREP per 30 days** to remain active.

**You have TWO options:**

**✈️ Option 1: Resume Flying**
Simply file a PIREP via the pilot portal or in Infinite Flight to stay on the active roster.

**📝 Option 2: File a Leave of Absence (LoA)**
If you are currently **not active in Infinite Flight (IF)** or unable to fly, submit an LoA using the format below:
- **Apply:** [Crew Centre](https://crew-center-qpva.vercel.app/pilot/settings)
*Open the Crew Centre, go to settings, and scroll down.*

⏳ **Deadline:**
You have **48 hours** from this message to either file a PIREP or submit an LoA. Failure to do so will result in **removal from the Akasa Air Virtual roster**.

Safe Skies,
**Akasa Air Virtual Management**"""


def get_db() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def is_authorized(member: discord.Member) -> bool:
    return any(role.id in (STAFF_ROLE_ID, EXEC_ROLE_ID) for role in member.roles)


def db_get_all_pilot_discord_ids() -> list[int]:
    """Get all discord_ids from the pilot_database table."""
    try:
        res = get_db().table("pilot_database").select("discord_id, status").eq("status", "Active").execute()
        return [int(r["discord_id"]) for r in (res.data or [])]
    except Exception:
        return []


def db_get_last_pirep_date(discord_id: int):
    """Get the most recent PIREP filed_at for a pilot."""
    try:
        res = get_db().table("pireps").select("filed_at").eq("discord_id", discord_id).order("filed_at", desc=True).limit(1).execute()
        if res.data:
            return res.data[0]["filed_at"]
        return None
    except Exception:
        return None


# ================= COG =================

class InactivityCheck(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="inactivitycheck",
        description="Check all active pilots for inactivity and DM those with no PIREP in 30 days (staff only)"
    )
    async def inactivitycheck(self, interaction: discord.Interaction):
        if not is_authorized(interaction.user):
            return await interaction.response.send_message(
                "❌ Only Staff and Executive Team can run this command.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        cutoff = datetime.now(timezone.utc) - timedelta(days=INACTIVITY_DAYS)
        pilot_ids = db_get_all_pilot_discord_ids()

        if not pilot_ids:
            return await interaction.followup.send(
                "⚠️ No active pilots found in the database.", ephemeral=True
            )

        dm_sent = 0
        dm_failed = 0
        active_count = 0
        inactive_ids = []

        for discord_id in pilot_ids:
            last_pirep_raw = db_get_last_pirep_date(discord_id)

            if last_pirep_raw:
                last_pirep = datetime.fromisoformat(
                    str(last_pirep_raw).replace("Z", "+00:00").replace(" ", "T")
                )
                if last_pirep.tzinfo is None:
                    last_pirep = last_pirep.replace(tzinfo=timezone.utc)
                if last_pirep >= cutoff:
                    active_count += 1
                    continue

            # Inactive — DM them
            inactive_ids.append(discord_id)
            try:
                user = await self.bot.fetch_user(discord_id)
                await user.send(INACTIVITY_MESSAGE)
                dm_sent += 1
            except discord.Forbidden:
                dm_failed += 1
            except discord.NotFound:
                dm_failed += 1
            except Exception:
                dm_failed += 1

        # Summary embed to staff
        embed = discord.Embed(
            title="⌛ Inactivity Check Complete",
            color=discord.Color.orange()
        )
        embed.add_field(name="✅ Active Pilots", value=str(active_count), inline=True)
        embed.add_field(name="⚠️ Inactive Pilots", value=str(len(inactive_ids)), inline=True)
        embed.add_field(name="📨 DMs Sent", value=str(dm_sent), inline=True)
        embed.add_field(name="❌ DMs Failed", value=str(dm_failed), inline=True)
        embed.add_field(name="👥 Total Checked", value=str(len(pilot_ids)), inline=True)
        embed.add_field(name="📅 Cutoff Date", value=f"<t:{int(cutoff.timestamp())}:D>", inline=True)

        if dm_failed > 0:
            embed.add_field(
                name="ℹ️ Note",
                value=f"{dm_failed} pilot(s) could not be DM'd — their DMs may be closed or they've left Discord.",
                inline=False
            )

        embed.set_footer(text=f"Run by {interaction.user} • AkasaAirVirtual Inactivity Check")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="checkpilot",
        description="Check a specific pilot's PIREP activity (staff only)"
    )
    @app_commands.describe(member="The pilot to check")
    async def checkpilot(self, interaction: discord.Interaction, member: discord.Member):
        if not is_authorized(interaction.user):
            return await interaction.response.send_message(
                "❌ Only Staff and Executive Team can run this command.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        cutoff = datetime.now(timezone.utc) - timedelta(days=INACTIVITY_DAYS)
        last_pirep_raw = db_get_last_pirep_date(member.id)

        embed = discord.Embed(
            title=f"📊 Activity Check — {member.display_name}",
            color=discord.Color.orange()
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        if last_pirep_raw:
            last_pirep = datetime.fromisoformat(
                str(last_pirep_raw).replace("Z", "+00:00").replace(" ", "T")
            )
            if last_pirep.tzinfo is None:
                last_pirep = last_pirep.replace(tzinfo=timezone.utc)

            timestamp = int(last_pirep.timestamp())
            is_active = last_pirep >= cutoff

            embed.color = discord.Color.green() if is_active else discord.Color.red()
            embed.add_field(name="📅 Last PIREP", value=f"<t:{timestamp}:F> (<t:{timestamp}:R>)", inline=False)
            embed.add_field(name="📊 Status", value="🟢 Active" if is_active else "🔴 Inactive (30+ days)", inline=True)
        else:
            embed.color = discord.Color.red()
            embed.add_field(name="📅 Last PIREP", value="No PIREPs filed", inline=False)
            embed.add_field(name="📊 Status", value="🔴 Inactive (no PIREPs)", inline=True)

        embed.set_footer(text="AkasaAirVirtual • Inactivity Check")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(InactivityCheck(bot))
