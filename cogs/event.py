import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
from datetime import datetime, timezone
import asyncio

class EventButtons(View):
    def __init__(self, attendees, max_users, embed_msg, event_time):
        super().__init__(timeout=None)
        self.attendees = attendees
        self.max_users = max_users
        self.embed_msg = embed_msg
        self.locked = False
        self.event_time = event_time

    async def update_embed(self):
        embed = self.embed_msg.embeds[0]

        # Unique attendees
        unique_users = list(dict.fromkeys(self.attendees))
        attending_text = "\n".join([u.mention for u in unique_users]) if unique_users else "No attendees yet"
        embed.set_field_at(1, name=f"Attending ({len(unique_users)}/{self.max_users})", value=attending_text, inline=False)

        # Countdown
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if not self.locked:
            remaining = max(int(self.event_time.timestamp()) - now_ts, 0)
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            embed.set_field_at(0, name="Event Time", value=f"{self.event_time.strftime('%A, %d %B %Y %I:%M %p')} | ⏳ {hours}h {minutes}m remaining", inline=False)

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


class Event(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="createevent", description="Create a Sesh style event")
    @app_commands.describe(
        title="Event title",
        datetime="Event time in YY-MM-DD HH:MM (24h)",
        description="Event description",
        channel="Channel to post event",
        max_attendees="Maximum attendees",
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
        max_attendees: int,
        on_create_mentions: discord.Role = None,
        on_start_mentions: discord.Role = None,
        image: str = None
    ):
        # parse datetime
        try:
            dt = datetime.strptime(datetime, "%y-%m-%d %H:%M")
            dt = dt.replace(tzinfo=timezone.utc)
        except:
            await interaction.response.send_message("Invalid datetime. Use `YY-MM-DD HH:MM` 24h format.", ephemeral=True)
            return

        # Embed
        embed = discord.Embed(
            title=f"🎉 {title}",
            description=description,
            color=discord.Color.orange()
        )
        embed.add_field(name="Event Time", value=dt.strftime("%A, %d %B %Y %I:%M %p") + " | ⏳ calculating...", inline=False)
        embed.add_field(name=f"Attending (0/{max_attendees})", value="No attendees yet", inline=False)
        embed.add_field(name="Host", value=interaction.user.mention, inline=False)

        if image:
            embed.set_image(url=image)

        mention_text = on_create_mentions.mention if on_create_mentions else ""
        msg = await channel.send(content=mention_text, embed=embed)

        attendees = []
        view = EventButtons(attendees, max_attendees, msg, dt)
        await msg.edit(view=view)

        await interaction.response.send_message(f"Event created in {channel.mention}", ephemeral=True)

        # Countdown
        now_ts = int(datetime.now(timezone.utc).timestamp())
        delay = int(dt.timestamp()) - now_ts

        reminders = [1800, 600, 300]  # 30m, 10m, 5m
        for reminder in reminders:
            if delay > reminder:
                await asyncio.sleep(delay - reminder)
                await channel.send(f"⏰ Event **{title}** starting in {reminder//60} minutes!")
                delay = reminder

        if delay > 0:
            await asyncio.sleep(delay)

        # Lock event and announce start
        view.locked = True
        start_embed = discord.Embed(title=f"🚀 {title} Started!", description=f"The event is now live!", color=discord.Color.orange())
        start_mention = on_start_mentions.mention if on_start_mentions else ""
        await channel.send(content=start_mention, embed=start_embed)
        await view.update_embed()


async def setup(bot):
    await bot.add_cog(Event(bot))
