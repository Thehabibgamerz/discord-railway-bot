import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import sqlite3
import os
from datetime import datetime, timezone, timedelta

STAFF_ROLE_ID = 1389824693388837035
IST = timezone(timedelta(hours=5, minutes=30))

DB_PATH = os.path.join(os.path.dirname(__file__), "events.db")


def is_staff(member: discord.Member) -> bool:
    return any(role.id == STAFF_ROLE_ID for role in member.roles)


# ================= DB HELPERS =================

def db_get_event_leaderboard(guild_id: int, limit: int = 10):
    """Top members by total events attended."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT a.user_id, COUNT(a.event_id) as total_events
            FROM attendees a
            JOIN events e ON a.event_id = e.event_id
            WHERE e.guild_id = ?
            GROUP BY a.user_id
            ORDER BY total_events DESC
            LIMIT ?
        """, (guild_id, limit)).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def db_get_active_events(guild_id: int):
    """Events that haven't started yet (upcoming)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM events
            WHERE guild_id = ? AND started = 0
            ORDER BY event_time_utc ASC
        """, (guild_id,)).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def db_get_event_attendees(event_id: int):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT user_id FROM attendees WHERE event_id = ?", (event_id,)
        ).fetchall()
        conn.close()
        return [r["user_id"] for r in rows]
    except Exception:
        return []


def db_get_user_events(guild_id: int, user_id: int):
    """All events a specific user has attended."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT e.title, e.event_time_utc, e.started
            FROM attendees a
            JOIN events e ON a.event_id = e.event_id
            WHERE e.guild_id = ? AND a.user_id = ?
            ORDER BY e.event_time_utc DESC
        """, (guild_id, user_id)).fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def db_get_all_events_count(guild_id: int):
    try:
        conn = sqlite3.connect(DB_PATH)
        total = conn.execute(
            "SELECT COUNT(*) FROM events WHERE guild_id = ?", (guild_id,)
        ).fetchone()[0]
        completed = conn.execute(
            "SELECT COUNT(*) FROM events WHERE guild_id = ? AND started = 1", (guild_id,)
        ).fetchone()[0]
        conn.close()
        return total, completed
    except Exception:
        return 0, 0


# ================= VIEWS =================

class LeaderboardView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="🏆 Leaderboard", style=discord.ButtonStyle.primary, custom_id="evlb_leaderboard")
    async def leaderboard(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)

        rows = db_get_event_leaderboard(interaction.guild.id)

        if not rows:
            return await interaction.followup.send(
                "⚠️ No event attendance data yet.", ephemeral=True
            )

        total_events, completed = db_get_all_events_count(interaction.guild.id)

        embed = discord.Embed(
            title="🏆 Event Attendance Leaderboard",
            description=f"**Total Events:** {total_events} · **Completed:** {completed}",
            color=discord.Color.orange()
        )

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, row in enumerate(rows):
            member = interaction.guild.get_member(row["user_id"])
            name = member.display_name if member else f"<@{row['user_id']}>"
            medal = medals[i] if i < 3 else f"**#{i + 1}**"
            count = row["total_events"]
            lines.append(f"{medal} {name} — **{count}** event{'s' if count != 1 else ''}")

        embed.add_field(name="\u200b", value="\n".join(lines), inline=False)
        embed.set_footer(text="AkasaAirVirtual • Event Leaderboard")
        await interaction.followup.send(embed=embed, ephemeral=False)

    @discord.ui.button(label="📅 Upcoming Events", style=discord.ButtonStyle.success, custom_id="evlb_upcoming")
    async def upcoming(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)

        events = db_get_active_events(interaction.guild.id)

        if not events:
            return await interaction.followup.send(
                "⚠️ No upcoming events right now.", ephemeral=True
            )

        embed = discord.Embed(
            title="📅 Upcoming Events",
            color=discord.Color.orange()
        )

        for event in events[:10]:
            event_time = datetime.fromisoformat(event["event_time_utc"])
            timestamp = int(event_time.timestamp())
            attendees = db_get_event_attendees(event["event_id"])
            host = interaction.guild.get_member(event["host_id"])
            host_name = host.display_name if host else f"<@{event['host_id']}>"

            embed.add_field(
                name=f"🎉 {event['title']}",
                value=(
                    f"📅 <t:{timestamp}:F> (<t:{timestamp}:R>)\n"
                    f"👥 **{len(attendees)}** attending\n"
                    f"🎙️ Host: {host_name}"
                ),
                inline=False
            )

        embed.set_footer(text="AkasaAirVirtual • Event Leaderboard")
        await interaction.followup.send(embed=embed, ephemeral=False)

    @discord.ui.button(label="👥 Event Participants", style=discord.ButtonStyle.secondary, custom_id="evlb_participants")
    async def participants(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)

        events = db_get_active_events(interaction.guild.id)

        if not events:
            return await interaction.followup.send(
                "⚠️ No upcoming events to show participants for.", ephemeral=True
            )

        # Show participants for the next upcoming event
        next_event = events[0]
        attendee_ids = db_get_event_attendees(next_event["event_id"])
        event_time = datetime.fromisoformat(next_event["event_time_utc"])
        timestamp = int(event_time.timestamp())

        embed = discord.Embed(
            title=f"👥 Participants — {next_event['title']}",
            description=f"📅 <t:{timestamp}:F>",
            color=discord.Color.blue()
        )

        if attendee_ids:
            lines = []
            for i, uid in enumerate(attendee_ids):
                member = interaction.guild.get_member(uid)
                name = member.mention if member else f"<@{uid}>"
                lines.append(f"`#{i + 1}` {name}")

            # Cap at 40 to avoid embed limits
            display = lines[:40]
            if len(attendee_ids) > 40:
                display.append(f"*…and {len(attendee_ids) - 40} more*")

            embed.add_field(
                name=f"✅ Attending ({len(attendee_ids)})",
                value="\n".join(display),
                inline=False
            )
        else:
            embed.add_field(name="✅ Attending", value="No attendees yet.", inline=False)

        embed.set_footer(text="AkasaAirVirtual • Event Leaderboard")
        await interaction.followup.send(embed=embed, ephemeral=False)

    @discord.ui.button(label="📊 My Stats", style=discord.ButtonStyle.secondary, custom_id="evlb_mystats")
    async def my_stats(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)

        events = db_get_user_events(interaction.guild.id, interaction.user.id)

        embed = discord.Embed(
            title=f"📊 Event Stats — {interaction.user.display_name}",
            color=discord.Color.orange()
        )

        total = len(events)
        completed = sum(1 for e in events if e["started"])
        upcoming = total - completed

        embed.add_field(name="🎉 Total Attended", value=str(total), inline=True)
        embed.add_field(name="✅ Completed", value=str(completed), inline=True)
        embed.add_field(name="📅 Upcoming", value=str(upcoming), inline=True)

        if events:
            recent = events[:5]
            lines = []
            for e in recent:
                event_time = datetime.fromisoformat(e["event_time_utc"])
                timestamp = int(event_time.timestamp())
                status = "✅" if e["started"] else "📅"
                lines.append(f"{status} **{e['title']}** — <t:{timestamp}:d>")
            embed.add_field(
                name="🕒 Recent Events",
                value="\n".join(lines),
                inline=False
            )

        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text="AkasaAirVirtual • Event Leaderboard")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.secondary, custom_id="evlb_refresh")
    async def refresh(self, interaction: discord.Interaction, button: Button):
        events = db_get_active_events(interaction.guild.id)
        rows = db_get_event_leaderboard(interaction.guild.id, limit=3)
        total_events, completed = db_get_all_events_count(interaction.guild.id)

        embed = build_panel_embed(interaction.guild, events, rows, total_events, completed)
        await interaction.response.edit_message(embed=embed, view=self)


def build_panel_embed(guild: discord.Guild, events, top_rows, total_events, completed):
    embed = discord.Embed(
        title="🎉 Akasa Air Virtual — Event Leaderboard",
        description=(
            "Track event attendance, upcoming events, and top participants.\n\n"
            "🏆 **Leaderboard** — Top attendees of all time\n"
            "📅 **Upcoming Events** — All scheduled events\n"
            "👥 **Event Participants** — Who's attending the next event\n"
            "📊 **My Stats** — Your personal event history\n"
            "🔄 **Refresh** — Update this panel"
        ),
        color=discord.Color.orange()
    )

    embed.add_field(
        name="📊 Server Stats",
        value=(
            f"🎉 Total Events: **{total_events}**\n"
            f"✅ Completed: **{completed}**\n"
            f"📅 Upcoming: **{total_events - completed}**"
        ),
        inline=True
    )

    if top_rows:
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, row in enumerate(top_rows):
            member = guild.get_member(row["user_id"])
            name = member.display_name if member else f"<@{row['user_id']}>"
            lines.append(f"{medals[i] if i < 3 else f'#{i+1}'} {name} — **{row['total_events']}** events")
        embed.add_field(name="🏆 Top Attendees", value="\n".join(lines), inline=True)

    if events:
        next_event = events[0]
        event_time = datetime.fromisoformat(next_event["event_time_utc"])
        timestamp = int(event_time.timestamp())
        attendees = db_get_event_attendees(next_event["event_id"])
        embed.add_field(
            name="📅 Next Event",
            value=(
                f"**{next_event['title']}**\n"
                f"<t:{timestamp}:F>\n"
                f"👥 {len(attendees)} attending"
            ),
            inline=False
        )

    embed.set_footer(text="AkasaAirVirtual • Event Leaderboard • Click a button below")
    return embed


# ================= COG =================

class EventLeaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="eventleaderboard_panel", description="Send the live event leaderboard panel (staff only)")
    @app_commands.describe(channel="Channel to post the panel in")
    async def eventleaderboard_panel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff can send the event leaderboard panel.", ephemeral=True
            )

        events = db_get_active_events(interaction.guild.id)
        top_rows = db_get_event_leaderboard(interaction.guild.id, limit=3)
        total_events, completed = db_get_all_events_count(interaction.guild.id)

        embed = build_panel_embed(interaction.guild, events, top_rows, total_events, completed)
        view = LeaderboardView(interaction.guild.id)

        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            f"✅ Event leaderboard panel sent in {channel.mention}", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(EventLeaderboard(bot))
    bot.add_view(LeaderboardView(0))
