import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta
import os

STAFF_ROLE_ID = 1389824693388837035
EXEC_ROLE_ID = 1389824452778262589

SUPABASE_URL = "https://xljanwcgesjhdoaavmuo.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


def get_db() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def is_authorized(member: discord.Member) -> bool:
    return any(role.id in (STAFF_ROLE_ID, EXEC_ROLE_ID) for role in member.roles)


def parse_time(raw) -> datetime:
    return datetime.fromisoformat(
        str(raw).replace("Z", "+00:00").replace(" ", "T")
    )


# ================= DB HELPERS =================

def db_get_upcoming_events(guild_id: int, limit: int = 10):
    try:
        res = get_db().table("events").select("*").eq("guild_id", guild_id).eq("started", 0).order("event_time_utc").limit(limit).execute()
        return res.data or []
    except Exception:
        return []


def db_get_recent_events(guild_id: int, limit: int = 5):
    try:
        res = get_db().table("events").select("*").eq("guild_id", guild_id).eq("started", 1).order("event_time_utc", desc=True).limit(limit).execute()
        return res.data or []
    except Exception:
        return []


def db_get_attendees(event_id: int) -> list:
    try:
        res = get_db().table("attendees").select("user_id").eq("event_id", event_id).execute()
        return [r["user_id"] for r in (res.data or [])]
    except Exception:
        return []


def db_get_event_counts(guild_id: int):
    try:
        total = get_db().table("events").select("event_id", count="exact").eq("guild_id", guild_id).execute().count or 0
        upcoming = get_db().table("events").select("event_id", count="exact").eq("guild_id", guild_id).eq("started", 0).execute().count or 0
        completed = total - upcoming
        return total, upcoming, completed
    except Exception:
        return 0, 0, 0


# ================= EMBED BUILDERS =================

def build_schedule_embed(guild: discord.Guild, events: list, total: int, upcoming: int, completed: int) -> discord.Embed:
    embed = discord.Embed(
        title="📅 Akasa Air Virtual — Event Schedule",
        color=discord.Color.orange()
    )

    embed.add_field(
        name="📊 Overview",
        value=(
            f"🎉 Total Events: **{total}**\n"
            f"📅 Upcoming: **{upcoming}**\n"
            f"✅ Completed: **{completed}**"
        ),
        inline=True
    )

    if not events:
        embed.add_field(
            name="📅 Upcoming Events",
            value="No upcoming events scheduled.",
            inline=False
        )
    else:
        lines = []
        for e in events:
            event_time = parse_time(e["event_time_utc"])
            timestamp = int(event_time.timestamp())
            attendees = db_get_attendees(e["event_id"])
            host = guild.get_member(int(e["host_id"]))
            host_name = host.display_name if host else f"<@{e['host_id']}>"

            lines.append(
                f"**🎉 {e['title']}**\n"
                f"📅 <t:{timestamp}:F> • <t:{timestamp}:R>\n"
                f"👥 {len(attendees)} attending • 🎙️ {host_name}"
            )

        embed.add_field(
            name=f"📅 Upcoming Events ({len(events)})",
            value="\n\n".join(lines[:5]),
            inline=False
        )

    embed.set_footer(text="AkasaAirVirtual • Event Schedule • Click Refresh to update")
    return embed


# ================= VIEW =================

class EventScheduleView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.primary, custom_id="sched_refresh")
    async def refresh(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        events = db_get_upcoming_events(interaction.guild.id)
        total, upcoming, completed = db_get_event_counts(interaction.guild.id)
        embed = build_schedule_embed(interaction.guild, events, total, upcoming, completed)
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="📋 All Upcoming", style=discord.ButtonStyle.secondary, custom_id="sched_all_upcoming")
    async def all_upcoming(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        events = db_get_upcoming_events(interaction.guild.id, limit=25)

        if not events:
            return await interaction.followup.send("⚠️ No upcoming events.", ephemeral=True)

        embed = discord.Embed(
            title="📅 All Upcoming Events",
            color=discord.Color.orange()
        )

        for e in events:
            event_time = parse_time(e["event_time_utc"])
            timestamp = int(event_time.timestamp())
            attendees = db_get_attendees(e["event_id"])
            host = interaction.guild.get_member(int(e["host_id"]))
            host_name = host.display_name if host else f"<@{e['host_id']}>"

            embed.add_field(
                name=f"🎉 {e['title']}",
                value=(
                    f"📅 <t:{timestamp}:F>\n"
                    f"⏰ <t:{timestamp}:R>\n"
                    f"👥 **{len(attendees)}** attending · 🎙️ {host_name}"
                ),
                inline=False
            )

        embed.set_footer(text="AkasaAirVirtual • Event Schedule")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="✅ Past Events", style=discord.ButtonStyle.secondary, custom_id="sched_past")
    async def past_events(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        events = db_get_recent_events(interaction.guild.id, limit=10)

        if not events:
            return await interaction.followup.send("⚠️ No completed events yet.", ephemeral=True)

        embed = discord.Embed(
            title="✅ Recent Completed Events",
            color=discord.Color.green()
        )

        for e in events:
            event_time = parse_time(e["event_time_utc"])
            timestamp = int(event_time.timestamp())
            attendees = db_get_attendees(e["event_id"])
            host = interaction.guild.get_member(int(e["host_id"]))
            host_name = host.display_name if host else f"<@{e['host_id']}>"

            embed.add_field(
                name=f"✅ {e['title']}",
                value=(
                    f"📅 <t:{timestamp}:D>\n"
                    f"👥 **{len(attendees)}** attended · 🎙️ {host_name}"
                ),
                inline=False
            )

        embed.set_footer(text="AkasaAirVirtual • Event Schedule")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="👥 Next Event Attendees", style=discord.ButtonStyle.success, custom_id="sched_next_attendees")
    async def next_attendees(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        events = db_get_upcoming_events(interaction.guild.id, limit=1)

        if not events:
            return await interaction.followup.send("⚠️ No upcoming events.", ephemeral=True)

        next_event = events[0]
        attendee_ids = db_get_attendees(next_event["event_id"])
        event_time = parse_time(next_event["event_time_utc"])
        timestamp = int(event_time.timestamp())

        embed = discord.Embed(
            title=f"👥 {next_event['title']} — Attendees",
            description=f"📅 <t:{timestamp}:F>",
            color=discord.Color.blue()
        )

        if attendee_ids:
            lines = []
            for i, uid in enumerate(attendee_ids[:40]):
                member = interaction.guild.get_member(int(uid))
                name = member.mention if member else f"<@{uid}>"
                lines.append(f"`#{i+1}` {name}")
            if len(attendee_ids) > 40:
                lines.append(f"*…and {len(attendee_ids) - 40} more*")
            embed.add_field(name=f"✅ Attending ({len(attendee_ids)})", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="✅ Attending", value="No attendees yet — be the first!", inline=False)

        embed.set_footer(text="AkasaAirVirtual • Event Schedule")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="📊 Stats", style=discord.ButtonStyle.secondary, custom_id="sched_stats", row=1)
    async def stats(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)

        total, upcoming, completed = db_get_event_counts(interaction.guild.id)
        events = db_get_upcoming_events(interaction.guild.id, limit=1)

        embed = discord.Embed(
            title="📊 Event Statistics",
            color=discord.Color.orange()
        )

        embed.add_field(name="🎉 Total Events", value=str(total), inline=True)
        embed.add_field(name="📅 Upcoming", value=str(upcoming), inline=True)
        embed.add_field(name="✅ Completed", value=str(completed), inline=True)

        if events:
            next_event = events[0]
            event_time = parse_time(next_event["event_time_utc"])
            timestamp = int(event_time.timestamp())
            attendees = db_get_attendees(next_event["event_id"])
            embed.add_field(
                name="🔜 Next Event",
                value=(
                    f"**{next_event['title']}**\n"
                    f"<t:{timestamp}:F>\n"
                    f"👥 {len(attendees)} attending"
                ),
                inline=False
            )

        embed.set_footer(text="AkasaAirVirtual • Event Schedule")
        await interaction.followup.send(embed=embed, ephemeral=True)


# ================= COG =================

class EventSchedulePanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="event_schedule_panel", description="Send the Event Schedule panel (staff only)")
    @app_commands.describe(
        channel="Channel to post the panel in",
        image="Optional banner image URL"
    )
    async def event_schedule_panel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        image: str = None
    ):
        if not is_authorized(interaction.user):
            return await interaction.response.send_message(
                "❌ Only Staff and Executive Team can send this panel.", ephemeral=True
            )

        events = db_get_upcoming_events(interaction.guild.id)
        total, upcoming, completed = db_get_event_counts(interaction.guild.id)

        embed = build_schedule_embed(interaction.guild, events, total, upcoming, completed)

        if image:
            embed.set_image(url=image)

        view = EventScheduleView(interaction.guild.id)
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            f"✅ Event Schedule panel sent in {channel.mention}", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(EventSchedulePanel(bot))
    bot.add_view(EventScheduleView(0))
