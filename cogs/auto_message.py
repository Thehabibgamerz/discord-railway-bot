import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
from supabase import create_client, Client
from datetime import datetime, timezone
import os
import re

STAFF_ROLE_ID = 1389824693388837035
EXEC_ROLE_ID = 1389824452778262589

SUPABASE_URL = "https://xljanwcgesjhdoaavmuo.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


def get_db() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def is_authorized(member: discord.Member) -> bool:
    return any(role.id in (STAFF_ROLE_ID, EXEC_ROLE_ID) for role in member.roles)


def parse_duration(text: str):
    text = text.strip().lower()
    match = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", text)
    if not match or not any(match.groups()):
        return None
    total = 0
    if match.group(1):
        total += int(match.group(1)) * 3600
    if match.group(2):
        total += int(match.group(2)) * 60
    if match.group(3):
        total += int(match.group(3))
    return total if total > 0 else None


def format_duration(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if s:
        parts.append(f"{s}s")
    return " ".join(parts) or "0s"


# ================= SUPABASE HELPERS =================

def db_get_all_schedules(guild_id: int):
    try:
        res = get_db().table("auto_messages").select("*").eq("guild_id", guild_id).eq("active", True).execute()
        return res.data or []
    except Exception:
        return []


def db_get_all_schedules_global():
    try:
        res = get_db().table("auto_messages").select("*").eq("active", True).execute()
        return res.data or []
    except Exception:
        return []


def db_add_schedule(guild_id, channel_id, message, interval_seconds, label, created_by):
    now = datetime.now(timezone.utc).isoformat()
    res = get_db().table("auto_messages").insert({
        "guild_id": guild_id,
        "channel_id": channel_id,
        "message": message,
        "interval_seconds": interval_seconds,
        "label": label,
        "created_by": created_by,
        "active": True,
        "created_at": now,
        "last_sent": now
    }).execute()
    return res.data[0] if res.data else None


def db_delete_schedule(schedule_id, guild_id):
    get_db().table("auto_messages").update({"active": False}).eq("id", schedule_id).eq("guild_id", guild_id).execute()


def db_update_last_sent(schedule_id):
    get_db().table("auto_messages").update({
        "last_sent": datetime.now(timezone.utc).isoformat()
    }).eq("id", schedule_id).execute()


def db_update_schedule(schedule_id, guild_id, updates):
    get_db().table("auto_messages").update(updates).eq("id", schedule_id).eq("guild_id", guild_id).execute()


# ================= MODALS =================

class SetAutoMessageModal(Modal):
    def __init__(self):
        super().__init__(title="Set Auto Message")
        self.label_field = TextInput(label="Label", placeholder="e.g. Rules Reminder", max_length=50)
        self.channel_id = TextInput(label="Channel ID", placeholder="Right-click channel → Copy ID", max_length=20)
        self.message = TextInput(label="Message", style=discord.TextStyle.paragraph, placeholder="Message to send automatically...", max_length=2000)
        self.duration = TextInput(label="Interval (e.g. 1h, 30m, 2h30m)", placeholder="Minimum 5 minutes", max_length=10)
        self.add_item(self.label_field)
        self.add_item(self.channel_id)
        self.add_item(self.message)
        self.add_item(self.duration)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel_id.value.strip())
        except ValueError:
            return await interaction.response.send_message("❌ Invalid channel ID.", ephemeral=True)

        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            return await interaction.response.send_message("❌ Channel not found.", ephemeral=True)

        interval = parse_duration(self.duration.value)
        if not interval:
            return await interaction.response.send_message(
                "❌ Invalid duration. Use formats like `1h`, `30m`, `2h30m`.", ephemeral=True
            )
        if interval < 300:
            return await interaction.response.send_message(
                "❌ Minimum interval is 5 minutes.", ephemeral=True
            )

        try:
            record = db_add_schedule(
                guild_id=interaction.guild.id,
                channel_id=channel_id,
                message=self.message.value,
                interval_seconds=interval,
                label=self.label_field.value.strip(),
                created_by=interaction.user.id
            )
        except Exception as e:
            return await interaction.response.send_message(f"❌ Failed to save: `{e}`", ephemeral=True)

        embed = discord.Embed(title="✅ Auto Message Scheduled", color=discord.Color.green())
        embed.add_field(name="📌 Label", value=self.label_field.value.strip(), inline=True)
        embed.add_field(name="📢 Channel", value=channel.mention, inline=True)
        embed.add_field(name="⏱️ Every", value=format_duration(interval), inline=True)
        embed.add_field(name="💬 Message Preview", value=self.message.value[:200] + ("..." if len(self.message.value) > 200 else ""), inline=False)
        embed.add_field(name="🆔 Schedule ID", value=f"`{record['id'] if record else 'N/A'}`", inline=True)
        embed.set_footer(text=f"Set by {interaction.user} • AkasaAirVirtual")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class RemoveScheduleModal(Modal):
    def __init__(self):
        super().__init__(title="Remove Auto Message")
        self.schedule_id = TextInput(label="Schedule ID", placeholder="Use List Schedules to find the ID", max_length=10)
        self.add_item(self.schedule_id)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            sid = int(self.schedule_id.value.strip())
        except ValueError:
            return await interaction.response.send_message("❌ Invalid ID.", ephemeral=True)
        db_delete_schedule(sid, interaction.guild.id)
        await interaction.response.send_message(f"✅ Schedule `#{sid}` removed.", ephemeral=True)


class EditScheduleModal(Modal):
    def __init__(self):
        super().__init__(title="Edit Auto Message")
        self.schedule_id = TextInput(label="Schedule ID to edit", max_length=10)
        self.new_message = TextInput(label="New Message (blank = keep)", style=discord.TextStyle.paragraph, required=False, max_length=2000)
        self.new_interval = TextInput(label="New Interval e.g. 1h (blank = keep)", required=False, max_length=10)
        self.add_item(self.schedule_id)
        self.add_item(self.new_message)
        self.add_item(self.new_interval)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            sid = int(self.schedule_id.value.strip())
        except ValueError:
            return await interaction.response.send_message("❌ Invalid ID.", ephemeral=True)

        updates = {}
        if self.new_message.value.strip():
            updates["message"] = self.new_message.value.strip()
        if self.new_interval.value.strip():
            interval = parse_duration(self.new_interval.value)
            if not interval or interval < 300:
                return await interaction.response.send_message("❌ Invalid or too-short interval.", ephemeral=True)
            updates["interval_seconds"] = interval

        if not updates:
            return await interaction.response.send_message("⚠️ No changes made.", ephemeral=True)

        db_update_schedule(sid, interaction.guild.id, updates)
        await interaction.response.send_message(f"✅ Schedule `#{sid}` updated.", ephemeral=True)


# ================= PANEL VIEW =================

class AutoMessageView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def auth_check(self, interaction: discord.Interaction) -> bool:
        if not is_authorized(interaction.user):
            await interaction.response.send_message(
                "❌ Only Staff and Executive Team can manage auto messages.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Set Auto Message", emoji="➕", style=discord.ButtonStyle.success, custom_id="automsg_set")
    async def set_message(self, interaction: discord.Interaction, button: Button):
        if not await self.auth_check(interaction):
            return
        await interaction.response.send_modal(SetAutoMessageModal())

    @discord.ui.button(label="List Schedules", emoji="📋", style=discord.ButtonStyle.primary, custom_id="automsg_list")
    async def list_schedules(self, interaction: discord.Interaction, button: Button):
        if not await self.auth_check(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        schedules = db_get_all_schedules(interaction.guild.id)
        if not schedules:
            return await interaction.followup.send("⚠️ No active schedules.", ephemeral=True)

        embed = discord.Embed(title="📋 Active Auto Messages", color=discord.Color.orange())
        for s in schedules:
            ch = interaction.guild.get_channel(s["channel_id"])
            ch_text = ch.mention if ch else f"<#{s['channel_id']}>"
            by = interaction.guild.get_member(s.get("created_by", 0))
            by_name = by.display_name if by else "Unknown"
            embed.add_field(
                name=f"#{s['id']} — {s.get('label', 'Unnamed')}",
                value=(
                    f"📢 {ch_text} · ⏱️ Every **{format_duration(s['interval_seconds'])}**\n"
                    f"💬 {str(s['message'])[:80]}{'...' if len(str(s['message'])) > 80 else ''}\n"
                    f"👤 {by_name}"
                ),
                inline=False
            )
        embed.set_footer(text="AkasaAirVirtual • AutoMessage")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Edit Schedule", emoji="✏️", style=discord.ButtonStyle.secondary, custom_id="automsg_edit")
    async def edit_schedule(self, interaction: discord.Interaction, button: Button):
        if not await self.auth_check(interaction):
            return
        await interaction.response.send_modal(EditScheduleModal())

    @discord.ui.button(label="Remove Schedule", emoji="🗑️", style=discord.ButtonStyle.danger, custom_id="automsg_remove")
    async def remove_schedule(self, interaction: discord.Interaction, button: Button):
        if not await self.auth_check(interaction):
            return
        await interaction.response.send_modal(RemoveScheduleModal())


# ================= COG =================

class AutoMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_schedules.start()

    async def cog_unload(self):
        self.check_schedules.cancel()

    @tasks.loop(seconds=60)
    async def check_schedules(self):
        now = datetime.now(timezone.utc)
        for s in db_get_all_schedules_global():
            try:
                last_sent = datetime.fromisoformat(s["last_sent"])
                if (now - last_sent).total_seconds() >= s["interval_seconds"]:
                    channel = self.bot.get_channel(s["channel_id"])
                    if channel:
                        await channel.send(s["message"])
                        db_update_last_sent(s["id"])
            except Exception:
                continue

    @check_schedules.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="automessage_panel", description="Send the Auto Message management panel")
    @app_commands.describe(channel="Channel to post the panel in")
    async def automessage_panel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_authorized(interaction.user):
            return await interaction.response.send_message(
                "❌ Only Staff and Executive Team can send this panel.", ephemeral=True
            )

        embed = discord.Embed(
            title="⚙️ Akasa Air Virtual — Auto Message Manager",
            description=(
                "Manage automated recurring messages for your server.\n\n"
                "➕ **Set Auto Message** — Schedule a new recurring message\n"
                "📋 **List Schedules** — View all active scheduled messages\n"
                "✏️ **Edit Schedule** — Update an existing schedule\n"
                "🗑️ **Remove Schedule** — Delete a schedule\n\n"
                "**Duration formats:** `1h` · `30m` · `2h30m` · `45s`\n"
                "**Minimum interval:** 5 minutes\n\n"
                "*Access restricted to Staff and Executive Team.*"
            ),
            color=discord.Color.orange()
        )
        embed.set_footer(text="AkasaAirVirtual • Auto Message Manager")

        view = AutoMessageView()
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            f"✅ Auto Message panel sent in {channel.mention}", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(AutoMessage(bot))
    bot.add_view(AutoMessageView())
