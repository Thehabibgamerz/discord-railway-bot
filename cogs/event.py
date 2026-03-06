import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button
from datetime import datetime, timezone
import asyncio

class EventButtons(View):
    def __init__(self, attendees, max_users, embed_msg, unix_time):
        super().__init__(timeout=None)
        self.attendees = attendees
        self.max_users = max_users
        self.embed_msg = embed_msg
        self.locked = False
        self.unix_time = unix_time

    async def update_embed(self):
        embed = self.embed_msg.embeds[0]

        # Attendees unique
        unique_users = list(dict.fromkeys(self.attendees))
        attending_text = "\n".join([u.mention for u in unique_users]) if unique_users else "No attendees yet"
        embed.set_field_at(1, name=f"Attending ({len(unique_users)}/{self.max_users})", value=attending_text, inline=False)

        # Countdown
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if not self.locked:
            remaining = max(self.unix_time - now_ts, 0)
            embed.set_field_at(0, name="Event Time", value=f"<t:{self.unix_time}:F> | ⏳ {remaining//3600}h {(remaining%3600)//60}m remaining", inline=False)

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
        on_create_mentions="Role to mention on create (optional)",
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
        try:
            dt = datetime.strptime(datetime, "%y-%m-%d %H:%M")
            dt = dt.replace(tzinfo=timezone.utc)
            unix = int(dt.timestamp())
        except:
            await interaction.response.send_message("Invalid datetime. Use YY-MM-DD HH:MM (24h).", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🎉 {title}",
            description=description,
            color=discord.Color.orange()
        )
        embed.add_field(name="Event Time", value=f"<t:{unix}:F> | ⏳ calculating...", inline=False)
        embed.add_field(name=f"Attending (0/{max_attendees})", value="No attendees yet", inline=False)
        embed.add_field(name="Host", value=interaction.user.mention, inline=False)

        if image:
            embed.set_image(url=image)

        mention_text = on_create_mentions.mention if on_create_mentions else ""
        msg = await channel.send(content=mention_text, embed=embed)

        attendees = []
        view = EventButtons(attendees, max_attendees, msg, unix)
        await msg.edit(view=view)

        await interaction.response.send_message(f"Event created in {channel.mention}", ephemeral=True)

        # start countdown
        while True:
            now_ts = int(datetime.now(timezone.utc).timestamp())
            if now_ts >= unix:
                break
            await view.update_embed()
            await asyncio.sleep(30)  # update every 30 seconds

        # Lock event and announce start
        view.locked = True
        start_embed = discord.Embed(title=f"🚀 {title} Started!", description=f"The event is now live!", color=discord.Color.orange())
        start_mention = on_start_mentions.mention if on_start_mentions else ""
        await channel.send(content=start_mention, embed=start_embed)
        await view.update_embed()


async def setup(bot):
    await bot.add_cog(Event(bot))
