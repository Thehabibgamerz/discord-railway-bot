import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime


class Event(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="event", description="Create an event with timestamp")
    @app_commands.describe(
        title="Event title",
        description="Event description",
        time="Event time (YYYY-MM-DD HH:MM)",
        channel="Channel to send event",
        image="Optional image URL"
    )
    async def event(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        time: str,
        channel: discord.TextChannel,
        image: str = None
    ):

        # 🔒 Staff only
        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )

        # 🕒 Convert time → timestamp
        try:
            dt = datetime.strptime(time, "%Y-%m-%d %H:%M")
            timestamp = int(dt.timestamp())
        except ValueError:
            return await interaction.response.send_message(
                "❌ Invalid time format!\nUse: YYYY-MM-DD HH:MM",
                ephemeral=True
            )

        # 📦 Embed
        embed = discord.Embed(
            title=f"📅 {title}",
            description=description,
            color=discord.Color.orange()
        )

        # 🕒 Timestamp display
        embed.add_field(
            name="🕒 Event Time",
            value=f"📅 <t:{timestamp}:F>\n⏰ <t:{timestamp}:R>",
            inline=False
        )

        # 🖼️ Optional image
        if image:
            embed.set_image(url=image)

        # Footer
        embed.set_footer(
            text=f"Hosted by {interaction.user}",
            icon_url=interaction.user.display_avatar.url
        )

        # 📤 Send event
        await channel.send(embed=embed)

        await interaction.response.send_message(
            f"✅ Event created in {channel.mention}",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Event(bot))
