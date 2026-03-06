import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import asyncio
from datetime import datetime

class EventView(View):
    def __init__(self, attendees, embed_message):
        super().__init__(timeout=None)
        self.attendees = attendees
        self.embed_message = embed_message

    async def update_embed(self, interaction):
        embed = self.embed_message.embeds[0]

        if self.attendees:
            embed.set_field_at(
                0,
                name="Attending",
                value="\n".join([user.mention for user in self.attendees]),
                inline=False
            )
        else:
            embed.set_field_at(
                0,
                name="Attending",
                value="No one yet",
                inline=False
            )

        await self.embed_message.edit(embed=embed, view=self)

    @discord.ui.button(label="I'm Attending", style=discord.ButtonStyle.success, emoji="✅")
    async def attend(self, interaction: discord.Interaction, button: Button):

        if interaction.user not in self.attendees:
            self.attendees.append(interaction.user)

        await self.update_embed(interaction)
        await interaction.response.send_message("You are attending this event.", ephemeral=True)

    @discord.ui.button(label="Remove Me", style=discord.ButtonStyle.danger, emoji="❌")
    async def remove(self, interaction: discord.Interaction, button: Button):

        if interaction.user in self.attendees:
            self.attendees.remove(interaction.user)

        await self.update_embed(interaction)
        await interaction.response.send_message("You were removed from the event.", ephemeral=True)


class Event(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="createevent", description="Create a server event")
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

        try:
            # Expecting <t:unix:F> format
            timestamp = int(datetime.split(":")[1])
            event_time = datetime
        except:
            await interaction.response.send_message(
                "Use Discord timestamp format like: <t:1710000000:F>",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.orange()
        )

        embed.add_field(
            name="Event Time",
            value=event_time,
            inline=False
        )

        embed.add_field(
            name="Attending",
            value="No one yet",
            inline=False
        )

        embed.set_footer(text=f"Hosted by {interaction.user}")

        if image:
            embed.set_image(url=image)

        mention_text = on_create_mentions.mention if on_create_mentions else ""

        msg = await channel.send(
            content=mention_text,
            embed=embed
        )

        attendees = []

        view = EventView(attendees, msg)

        await msg.edit(view=view)

        await interaction.response.send_message(
            f"Event created in {channel.mention}",
            ephemeral=True
        )

        # WAIT UNTIL EVENT START
        unix_time = int(timestamp)
        delay = unix_time - int(datetime.now().timestamp())

        if delay > 0:

            await asyncio.sleep(delay)

            start_embed = discord.Embed(
                title="Event Started",
                description=f"**{title}** has now started!",
                color=discord.Color.orange()
            )

            mention = on_start_mentions.mention if on_start_mentions else ""

            await channel.send(
                content=mention,
                embed=start_embed
            )


async def setup(bot):
    await bot.add_cog(Event(bot))
