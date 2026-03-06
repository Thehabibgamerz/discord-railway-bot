import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
from datetime import datetime, timedelta
import asyncio
import random

IST_OFFSET = timedelta(hours=5, minutes=30)

class GiveawayView(View):
    def __init__(self, giveaway_data, message):
        super().__init__(timeout=None)
        self.giveaway_data = giveaway_data
        self.message = message  # Embed message to edit live

    async def update_embed(self):
        gd = self.giveaway_data
        end_time = gd["end_time"]
        now = datetime.now() + IST_OFFSET
        remaining = max(int((end_time - now).total_seconds()), 0)
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        seconds = remaining % 60
        countdown_text = f"⏱️ Time Remaining: {hours}h {minutes}m {seconds}s"

        participants = [f"<@{uid}>" for uid in gd["participants"]]
        participants_text = "\n".join(participants) if participants else "No participants yet"

        embed = discord.Embed(
            title=f"🎁 {gd['title']}",
            description=(
                f"📋 {gd['description']}\n\n"
                f"⏰ Ends on: {gd['end_time'].strftime('%A, %d %B %Y %I:%M %p')} IST\n\n"
                f"**Participants ({len(participants)}):**\n{participants_text}\n\n{countdown_text}"
            ),
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"Hosted by {gd['host']}", icon_url=gd['host'].display_avatar.url)
        if gd["image"]:
            embed.set_image(url=gd["image"])
        await self.message.edit(embed=embed)

    @discord.ui.button(label="🎉 Enter Giveaway", style=discord.ButtonStyle.success)
    async def enter(self, interaction: discord.Interaction, button: Button):
        user_id = interaction.user.id
        if user_id in self.giveaway_data["participants"]:
            await interaction.response.send_message("⚠️ You are already entered!", ephemeral=True)
            return
        self.giveaway_data["participants"].append(user_id)
        await self.update_embed()  # Update embed immediately
        await interaction.response.send_message("✅ You entered the giveaway!", ephemeral=True)

    @discord.ui.button(label="❌ Remove Me", style=discord.ButtonStyle.danger)
    async def remove(self, interaction: discord.Interaction, button: Button):
        user_id = interaction.user.id
        if user_id not in self.giveaway_data["participants"]:
            await interaction.response.send_message("⚠️ You are not entered!", ephemeral=True)
            return
        self.giveaway_data["participants"].remove(user_id)
        await self.update_embed()  # Update embed immediately
        await interaction.response.send_message("❌ You were removed from the giveaway.", ephemeral=True)


class GiveawayProLive(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_giveaways = {}  # channel_id: giveaway_data

    @app_commands.command(
        name="create_giveaway",
        description="Create a giveaway with live participants list and end time"
    )
    @app_commands.describe(
        title="Giveaway title",
        description="Giveaway description",
        ends_on="End time in YYYY-MM-DD HH:MM (IST)",
        channel="Channel to post",
        on_create_mentions="Optional role(s) to mention",
        image="Optional giveaway image URL"
    )
    async def create_giveaway(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        ends_on: str,
        channel: discord.TextChannel,
        on_create_mentions: discord.Role = None,
        image: str = None
    ):
        # Parse datetime
        try:
            end_time = datetime.strptime(ends_on, "%Y-%m-%d %H:%M")
        except ValueError:
            await interaction.response.send_message("❌ Invalid datetime format! Use YYYY-MM-DD HH:MM", ephemeral=True)
            return

        if end_time <= datetime.now() + IST_OFFSET:
            await interaction.response.send_message("❌ End time must be in the future.", ephemeral=True)
            return

        # Giveaway data
        giveaway_data = {
            "title": title,
            "description": description,
            "host": interaction.user,
            "end_time": end_time,
            "channel": channel,
            "ping_role": on_create_mentions.id if on_create_mentions else None,
            "image": image,
            "participants": []
        }

        self.active_giveaways[channel.id] = giveaway_data

        # Send initial embed
        embed = discord.Embed(
            title=f"🎁 {title}",
            description=f"📋 {description}\n\n⏰ Ends on: {end_time.strftime('%A, %d %B %Y %I:%M %p')} IST\n\n**Participants:** None yet",
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"Hosted by {interaction.user}", icon_url=interaction.user.display_avatar.url)
        if image:
            embed.set_image(url=image)

        mention_text = f"<@&{on_create_mentions.id}>" if on_create_mentions else ""
        message = await channel.send(content=mention_text, embed=embed)
        view = GiveawayView(giveaway_data, message)
        await message.edit(view=view)

        await interaction.response.send_message(f"✅ Giveaway created in {channel.mention}", ephemeral=True)

        # Countdown loop
        while True:
            await asyncio.sleep(30)
            now = datetime.now() + IST_OFFSET
            remaining = int((end_time - now).total_seconds())
            if remaining <= 0:
                break
            # update embed countdown only (participants updated via buttons)
            participants = [f"<@{uid}>" for uid in giveaway_data["participants"]]
            participants_text = "\n".join(participants) if participants else "No participants yet"
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            seconds = remaining % 60
            countdown_text = f"⏱️ Time Remaining: {hours}h {minutes}m {seconds}s"

            embed.description = (
                f"📋 {description}\n\n"
                f"⏰ Ends on: {end_time.strftime('%A, %d %B %Y %I:%M %p')} IST\n\n"
                f"**Participants ({len(participants)}):**\n{participants_text}\n\n{countdown_text}"
            )
            await message.edit(embed=embed)

        # End giveaway
        participants = giveaway_data["participants"]
        if not participants:
            await channel.send(f"❌ Giveaway **{title}** ended. No participants.")
        else:
            winner_id = random.choice(participants)
            await channel.send(f"🎉 Giveaway **{title}** ended! Winner: <@{winner_id}> 🏆")

        del self.active_giveaways[channel.id]


async def setup(bot):
    await bot.add_cog(GiveawayProLive(bot))
