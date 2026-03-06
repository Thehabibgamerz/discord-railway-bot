import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
from datetime import datetime, timedelta
import asyncio
import re

STAFF_ROLE_ID = 1389824693388837035  # Change to your staff role ID
IST_OFFSET = timedelta(hours=5, minutes=30)  # IST = UTC+5:30

# Natural-language datetime parser (local IST)
def parse_datetime(input_str: str):
    input_str = input_str.strip().lower()
    now = datetime.now() + IST_OFFSET
    
    # in Xh Ym format
    match = re.match(r"in (\d+)h(?: (\d+)m)?", input_str)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2)) if match.group(2) else 0
        return now + timedelta(hours=hours, minutes=minutes)
    
    # tomorrow HH:MM
    match = re.match(r"tomorrow (\d{1,2}):(\d{2})", input_str)
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2))
        dt = datetime(now.year, now.month, now.day, hour, minute) + timedelta(days=1)
        return dt
    
    # standard formats
    formats = [
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d %I:%M %p",
        "%d/%m/%Y %I:%M %p"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(input_str, fmt)
        except:
            continue
    return None

class EventButtons(View):
    def __init__(self, attendees, embed_msg, event_time, host):
        super().__init__(timeout=None)
        self.attendees = attendees
        self.embed_msg = embed_msg
        self.locked = False
        self.event_time = event_time
        self.host = host

    async def update_embed(self):
        embed = self.embed_msg.embeds[0]
        unique_users = list(dict.fromkeys(self.attendees))
        attending_text = "\n".join([u.mention for u in unique_users]) if unique_users else "No attendees yet"
        embed.set_field_at(1, name="Attending", value=attending_text, inline=False)

        # Countdown in IST
        now = datetime.now() + IST_OFFSET
        remaining = max(int((self.event_time - now).total_seconds()), 0)
        if not self.locked:
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            seconds = remaining % 60
            embed.set_field_at(
                0,
                name="Event Time (IST)",
                value=f"{self.event_time.strftime('%A, %d %B %Y %I:%M %p')} | ⏳ {hours}h {minutes}m {seconds}s remaining",
                inline=False
            )
        embed.set_footer(text=f"Host: {self.host}", icon_url=self.host.display_avatar.url)
        await self.embed_msg.edit(embed=embed, view=self)

    @discord.ui.button(label="I'm Attending", emoji="✅", style=discord.ButtonStyle.success)
    async def attend(self, interaction: discord.Interaction, button: Button):
        if self.locked:
            await interaction.response.send_message("Event attendance is locked.", ephemeral=True)
            return
        if interaction.user not in self.attendees:
            self.attendees.append(interaction.user)
        await self.update_embed()
        await interaction.response.send_message("You joined the event.", ephemeral=True)

    @discord.ui.button(label="Remove Me", emoji="❌", style=discord.ButtonStyle.danger)
    async def remove(self, interaction: discord.Interaction, button: Button):
        if interaction.user in self.attendees:
            self.attendees.remove(interaction.user)
        await self.update_embed()
        await interaction.response.send_message("You left the event.", ephemeral=True)

    @discord.ui.button(label="Edit Event", emoji="✏️", style=discord.ButtonStyle.secondary)
    async def edit_event(self, interaction: discord.Interaction, button: Button):
        if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("Only staff can edit events.", ephemeral=True)
            return
        modal = EventEditModal(self)
        await interaction.response.send_modal(modal)

class EventEditModal(Modal):
    def __init__(self, view: EventButtons):
        super().__init__(title="Edit Event")
        self.view_ref = view
        self.title_input = TextInput(label="Title", default=view.embed_msg.embeds[0].title, required=False)
        self.desc_input = TextInput(label="Description", style=discord.TextStyle.paragraph,
                                    default=view.embed_msg.embeds[0].description, required=False)
        self.time_input = TextInput(label="Datetime", default=view.event_time.strftime("%Y-%m-%d %H:%M"), required=False)
        self.add_item(self.title_input)
        self.add_item(self.desc_input)
        self.add_item(self.time_input)

    async def on_submit(self, interaction: discord.Interaction):
        embed = self.view_ref.embed_msg.embeds[0]
        if self.title_input.value:
            embed.title = self.title_input.value
        if self.desc_input.value:
            embed.description = self.desc_input.value
        if self.time_input.value:
            new_dt = parse_datetime(self.time_input.value)
            if new_dt:
                self.view_ref.event_time = new_dt
            else:
                await interaction.response.send_message("Invalid datetime format!", ephemeral=True)
                return
        await self.view_ref.update_embed()
        await interaction.response.send_message("Event updated successfully.", ephemeral=True)

class Event(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="createevent", description="Create PRO Sesh Event (IST Local Time)")
    @app_commands.describe(
        title="Event title",
        datetime="Datetime (e.g., 'tomorrow 12:00', 'in 2h30m', 'YYYY-MM-DD HH:MM')",
        description="Event description",
        channel="Channel to post event",
        on_create_mentions="Role to mention on creation (optional)",
        on_start_mentions="Role to mention on start (optional)",
        image="Optional banner image"
    )
    async def createevent(
        self,
        interaction: discord.Interaction,
        title: str,
        datetime: str,
        description: str,
        channel: discord.TextChannel,
        on_create_mentions: discord.Role = None,
        on_start_mentions: discord.Role = None,
        image: str = None
    ):
        dt = parse_datetime(datetime)
        if not dt:
            await interaction.response.send_message(
                "❌ Invalid datetime! Use 'tomorrow 12:00', 'in 2h30m', or 'YYYY-MM-DD HH:MM'.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"🎉 {title}",
            description=description,
            color=discord.Color.orange()
        )
        embed.add_field(
            name="Event Time (IST)",
            value=f"{dt.strftime('%A, %d %B %Y %I:%M %p')} | ⏳ calculating...",
            inline=False
        )
        embed.add_field(name="Attending", value="No attendees yet", inline=False)
        embed.set_footer(text=f"Host: {interaction.user}", icon_url=interaction.user.display_avatar.url)
        if image:
            embed.set_image(url=image)

        mention_text = on_create_mentions.mention if on_create_mentions else ""
        msg = await channel.send(content=mention_text, embed=embed)

        attendees = []
        view = EventButtons(attendees, msg, dt, interaction.user)
        await msg.edit(view=view)
        await interaction.response.send_message(f"✅ Event created in {channel.mention}", ephemeral=True)

        # Countdown loop in IST
        while True:
            now = datetime.now() + timedelta(hours=5, minutes=30)
            if now >= dt:
                break
            await view.update_embed()
            await asyncio.sleep(30)

        view.locked = True
        start_embed = discord.Embed(
            title=f"🚀 {title} Started!",
            description="The event is now live!",
            color=discord.Color.orange()
        )
        start_mention = on_start_mentions.mention if on_start_mentions else ""
        await channel.send(content=start_mention, embed=start_embed)
        await view.update_embed()

async def setup(bot):
    await bot.add_cog(Event(bot))
