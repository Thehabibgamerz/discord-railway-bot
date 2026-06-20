import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
from datetime import datetime, timedelta, timezone
import sqlite3
import re
import os

STAFF_ROLE_ID = 1389824693388837035  # Change to your staff role ID

# ✅ IST Timezone
IST = timezone(timedelta(hours=5, minutes=30))

DB_PATH = os.path.join(os.path.dirname(__file__), "events.db")

# NOTE: this uses a local SQLite file for persistence. On hosts with an
# ephemeral filesystem (e.g. Railway without a mounted volume), this file
# will be wiped on every redeploy, defeating the purpose of persistence.
# If that's the case for your setup, attach a Railway volume and point
# DB_PATH at a path inside it, or migrate this to Supabase/Postgres later.


# ================= DATABASE =================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            message_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            image_url TEXT,
            event_time_utc TEXT NOT NULL,
            host_id INTEGER NOT NULL,
            on_start_role_id INTEGER,
            locked INTEGER DEFAULT 0,
            started INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attendees (
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (event_id, user_id)
        )
    """)
    conn.commit()
    conn.close()


def db_create_event(guild_id, channel_id, title, description, image_url,
                     event_time_utc, host_id, on_start_role_id):
    conn = get_db()
    cur = conn.execute("""
        INSERT INTO events (guild_id, channel_id, title, description, image_url,
                             event_time_utc, host_id, on_start_role_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (guild_id, channel_id, title, description, image_url,
          event_time_utc, host_id, on_start_role_id))
    conn.commit()
    event_id = cur.lastrowid
    conn.close()
    return event_id


def db_set_message_id(event_id, message_id):
    conn = get_db()
    conn.execute("UPDATE events SET message_id = ? WHERE event_id = ?", (message_id, event_id))
    conn.commit()
    conn.close()


def db_get_event(event_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM events WHERE event_id = ?", (event_id,)).fetchone()
    conn.close()
    return row


def db_get_pending_events():
    """Events that haven't been marked as started yet."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM events WHERE started = 0").fetchall()
    conn.close()
    return rows


def db_get_due_events():
    conn = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    rows = conn.execute(
        "SELECT * FROM events WHERE started = 0 AND event_time_utc <= ?", (now_iso,)
    ).fetchall()
    conn.close()
    return rows


def db_mark_started(event_id):
    conn = get_db()
    conn.execute("UPDATE events SET started = 1, locked = 1 WHERE event_id = ?", (event_id,))
    conn.commit()
    conn.close()


def db_update_event(event_id, title=None, description=None, event_time_utc=None):
    conn = get_db()
    if title is not None:
        conn.execute("UPDATE events SET title = ? WHERE event_id = ?", (title, event_id))
    if description is not None:
        conn.execute("UPDATE events SET description = ? WHERE event_id = ?", (description, event_id))
    if event_time_utc is not None:
        conn.execute("UPDATE events SET event_time_utc = ? WHERE event_id = ?", (event_time_utc, event_id))
    conn.commit()
    conn.close()


def db_add_attendee(event_id, user_id):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO attendees (event_id, user_id) VALUES (?, ?)", (event_id, user_id)
    )
    conn.commit()
    conn.close()


def db_remove_attendee(event_id, user_id):
    conn = get_db()
    conn.execute("DELETE FROM attendees WHERE event_id = ? AND user_id = ?", (event_id, user_id))
    conn.commit()
    conn.close()


def db_get_attendees(event_id):
    conn = get_db()
    rows = conn.execute("SELECT user_id FROM attendees WHERE event_id = ?", (event_id,)).fetchall()
    conn.close()
    return [row["user_id"] for row in rows]


# ================= PARSER =================

def parse_datetime(input_str: str):
    input_str = input_str.strip().lower()
    now = datetime.now(IST)

    # in Xh Ym / in Xh / in Ym
    match = re.match(r"in (?:(\d+)h)? ?(?:(\d+)m)?$", input_str)
    if match and (match.group(1) or match.group(2)):
        hours = int(match.group(1)) if match.group(1) else 0
        minutes = int(match.group(2)) if match.group(2) else 0
        return now + timedelta(hours=hours, minutes=minutes)

    # tomorrow HH:MM
    match = re.match(r"tomorrow (\d{1,2}):(\d{2})", input_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        dt = datetime(now.year, now.month, now.day, hour, minute, tzinfo=IST) + timedelta(days=1)
        return dt

    # standard formats (assumed IST)
    formats = [
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d %I:%M %p",
        "%d/%m/%Y %I:%M %p"
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(input_str, fmt)
            return dt.replace(tzinfo=IST)
        except ValueError:
            continue

    return None


def is_staff(member: discord.Member) -> bool:
    return any(role.id == STAFF_ROLE_ID for role in member.roles)


# ================= EMBED BUILDER =================

def build_event_embed(event_row, attendee_ids, guild: discord.Guild):
    event_time = datetime.fromisoformat(event_row["event_time_utc"])
    timestamp = int(event_time.timestamp())

    embed = discord.Embed(
        title=f"🎉 {event_row['title']}",
        description=event_row["description"] or "",
        color=discord.Color.orange()
    )

    embed.add_field(
        name="🕒 Event Time",
        value=f"📅 <t:{timestamp}:F>\n⏰ <t:{timestamp}:R>",
        inline=False
    )

    if attendee_ids:
        mentions = "\n".join(f"<@{uid}>" for uid in attendee_ids)
        # Discord embed field values cap at 1024 characters
        if len(mentions) > 1000:
            shown = attendee_ids[:30]
            mentions = "\n".join(f"<@{uid}>" for uid in shown)
            mentions += f"\n…and {len(attendee_ids) - 30} more"
    else:
        mentions = "No attendees yet"

    embed.add_field(name=f"Attending ({len(attendee_ids)})", value=mentions, inline=False)

    host = guild.get_member(event_row["host_id"]) if guild else None
    host_name = host.display_name if host else f"User {event_row['host_id']}"
    host_icon = host.display_avatar.url if host else None
    embed.set_footer(text=f"Host: {host_name}", icon_url=host_icon)

    if event_row["image_url"]:
        embed.set_image(url=event_row["image_url"])

    if event_row["started"]:
        embed.color = discord.Color.green()

    return embed


# ================= VIEW =================

class EventButtons(View):
    """
    Fully stateless/restart-safe: every callback re-reads the event from
    the database using the event_id baked into each button's custom_id,
    rather than relying on in-memory Python state.
    """

    def __init__(self, event_id: int):
        super().__init__(timeout=None)
        self.event_id = event_id

        self.attend.custom_id = f"event_attend:{event_id}"
        self.remove.custom_id = f"event_remove:{event_id}"
        self.edit_event.custom_id = f"event_edit:{event_id}"

    async def refresh_message(self, interaction: discord.Interaction):
        event_row = db_get_event(self.event_id)
        if not event_row:
            return
        attendee_ids = db_get_attendees(self.event_id)
        embed = build_event_embed(event_row, attendee_ids, interaction.guild)
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="I'm Attending", emoji="✅", style=discord.ButtonStyle.success)
    async def attend(self, interaction: discord.Interaction, button: Button):
        event_row = db_get_event(self.event_id)
        if not event_row:
            return await interaction.response.send_message("⚠️ This event no longer exists.", ephemeral=True)
        if event_row["locked"]:
            return await interaction.response.send_message("🔒 This event has already started.", ephemeral=True)

        db_add_attendee(self.event_id, interaction.user.id)
        await self.refresh_message(interaction)
        await interaction.response.send_message("✅ You joined the event.", ephemeral=True)

    @discord.ui.button(label="Remove Me", emoji="❌", style=discord.ButtonStyle.danger)
    async def remove(self, interaction: discord.Interaction, button: Button):
        event_row = db_get_event(self.event_id)
        if not event_row:
            return await interaction.response.send_message("⚠️ This event no longer exists.", ephemeral=True)
        if event_row["locked"]:
            return await interaction.response.send_message("🔒 This event has already started.", ephemeral=True)

        db_remove_attendee(self.event_id, interaction.user.id)
        await self.refresh_message(interaction)
        await interaction.response.send_message("❌ You left the event.", ephemeral=True)

    @discord.ui.button(label="Edit Event", emoji="✏️", style=discord.ButtonStyle.secondary)
    async def edit_event(self, interaction: discord.Interaction, button: Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("Only staff can edit events.", ephemeral=True)

        event_row = db_get_event(self.event_id)
        if not event_row:
            return await interaction.response.send_message("⚠️ This event no longer exists.", ephemeral=True)

        await interaction.response.send_modal(EventEditModal(self.event_id, event_row))


# ================= EDIT MODAL =================

class EventEditModal(Modal):
    def __init__(self, event_id: int, event_row):
        super().__init__(title="Edit Event")
        self.event_id = event_id

        event_time = datetime.fromisoformat(event_row["event_time_utc"]).astimezone(IST)

        self.title_input = TextInput(label="Title", default=event_row["title"], required=False)
        self.desc_input = TextInput(
            label="Description",
            style=discord.TextStyle.paragraph,
            default=event_row["description"] or "",
            required=False
        )
        self.time_input = TextInput(
            label="Datetime (IST, e.g. 2026-06-25 18:00)",
            default=event_time.strftime("%Y-%m-%d %H:%M"),
            required=False
        )

        self.add_item(self.title_input)
        self.add_item(self.desc_input)
        self.add_item(self.time_input)

    async def on_submit(self, interaction: discord.Interaction):
        new_time_utc = None

        if self.time_input.value:
            new_dt = parse_datetime(self.time_input.value)
            if not new_dt:
                return await interaction.response.send_message("❌ Invalid datetime format!", ephemeral=True)
            new_time_utc = new_dt.astimezone(timezone.utc).isoformat()

        db_update_event(
            self.event_id,
            title=self.title_input.value or None,
            description=self.desc_input.value or None,
            event_time_utc=new_time_utc
        )

        event_row = db_get_event(self.event_id)
        attendee_ids = db_get_attendees(self.event_id)
        embed = build_event_embed(event_row, attendee_ids, interaction.guild)

        view = EventButtons(self.event_id)
        await interaction.message.edit(embed=embed, view=view)
        await interaction.response.send_message("✅ Event updated successfully.", ephemeral=True)


# ================= COG =================

class Event(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        init_db()

    async def cog_load(self):
        self.check_due_events.start()

    async def cog_unload(self):
        self.check_due_events.cancel()

    @tasks.loop(seconds=30)
    async def check_due_events(self):
        for event_row in db_get_due_events():
            await self._fire_event(event_row)

    @check_due_events.before_loop
    async def before_check_due_events(self):
        await self.bot.wait_until_ready()

    async def _fire_event(self, event_row):
        channel = self.bot.get_channel(event_row["channel_id"])
        if channel is None:
            db_mark_started(event_row["event_id"])  # avoid retrying forever on a dead channel
            return

        db_mark_started(event_row["event_id"])

        # Lock the original message's buttons
        if event_row["message_id"]:
            try:
                msg = await channel.fetch_message(event_row["message_id"])
                attendee_ids = db_get_attendees(event_row["event_id"])
                refreshed_row = db_get_event(event_row["event_id"])
                embed = build_event_embed(refreshed_row, attendee_ids, channel.guild)
                locked_view = EventButtons(event_row["event_id"])
                for child in locked_view.children:
                    if child.label in ("I'm Attending", "Remove Me"):
                        child.disabled = True
                await msg.edit(embed=embed, view=locked_view)
            except discord.NotFound:
                pass

        start_embed = discord.Embed(
            title=f"🚀 {event_row['title']} Started!",
            description="The event is now live!",
            color=discord.Color.orange()
        )

        mention_text = f"<@&{event_row['on_start_role_id']}>" if event_row["on_start_role_id"] else ""

        try:
            await channel.send(content=mention_text, embed=start_embed)
        except discord.Forbidden:
            pass

    @app_commands.command(name="createevent", description="Create a PRO event (IST input, auto-converted)")
    async def createevent(
        self,
        interaction: discord.Interaction,
        title: str,
        event_datetime: str,
        description: str,
        channel: discord.TextChannel,
        on_create_mentions: discord.Role = None,
        on_start_mentions: discord.Role = None,
        image: str = None
    ):
        dt = parse_datetime(event_datetime)

        if not dt:
            return await interaction.response.send_message(
                "❌ Invalid datetime! Use 'tomorrow 12:00', 'in 2h30m', or 'YYYY-MM-DD HH:MM'.",
                ephemeral=True
            )

        event_time_utc = dt.astimezone(timezone.utc).isoformat()

        event_id = db_create_event(
            guild_id=interaction.guild.id,
            channel_id=channel.id,
            title=title,
            description=description,
            image_url=image,
            event_time_utc=event_time_utc,
            host_id=interaction.user.id,
            on_start_role_id=on_start_mentions.id if on_start_mentions else None
        )

        event_row = db_get_event(event_id)
        embed = build_event_embed(event_row, [], interaction.guild)

        mention_text = on_create_mentions.mention if on_create_mentions else ""

        try:
            msg = await channel.send(content=mention_text, embed=embed)
        except discord.Forbidden:
            return await interaction.response.send_message(
                f"❌ I do not have permission to send messages in {channel.mention}.", ephemeral=True
            )

        db_set_message_id(event_id, msg.id)

        view = EventButtons(event_id)
        await msg.edit(view=view)

        await interaction.response.send_message(
            f"✅ Event created in {channel.mention}",
            ephemeral=True
        )

    async def restore_views(self):
        """Re-attach persistent views for every not-yet-started event on startup."""
        for event_row in db_get_pending_events():
            if event_row["message_id"]:
                self.bot.add_view(EventButtons(event_row["event_id"]), message_id=event_row["message_id"])


async def setup(bot):
    cog = Event(bot)
    await bot.add_cog(cog)
    await cog.restore_views()
