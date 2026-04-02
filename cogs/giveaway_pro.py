import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
from datetime import datetime, timedelta, timezone
import asyncio
import random

# ✅ IST timezone
IST = timezone(timedelta(hours=5, minutes=30))


class GiveawayView(View):
    def __init__(self, giveaway_data, message):
        super().__init__(timeout=None)
        self.giveaway_data = giveaway_data
        self.message = message

    async def update_embed(self):
        gd = self.giveaway_data

        # ✅ Convert IST → UTC → timestamp
        timestamp = int(gd["end_time"].astimezone(timezone.utc).timestamp())

        participants = [f"<@{uid}>" for uid in gd["participants"]]
        participants_text = "\n".join(participants) if participants else "No participants yet"

        embed = discord.Embed(
            title=f"🎁 {gd['title']}",
            description=(
                f"📋 {gd['description']}\n\n"
                f"🕒 Ends:\n📅 <t:{timestamp}:F>\n⏰ <t:{timestamp}:R>\n\n"
                f"**Participants ({len(participants)}):**\n{participants_text}"
            ),
            color=discord.Color.orange()
        )

        embed.set_footer(
            text=f"Hosted by {gd['host']}",
            icon_url=gd['host'].display_avatar.url
        )

        if gd["image"]:
            embed.set_image(url=gd["image"])

        await self.message.edit(embed=embed, view=self)

    @discord.ui.button(label="🎉 Enter Giveaway", style=discord.ButtonStyle.success)
    async def enter(self, interaction: discord.Interaction, button: Button):
        user_id = interaction.user.id

        if user_id in self.giveaway_data["participants"]:
            return await interaction.response.send_message("⚠️ You are already entered!", ephemeral=True)

        self.giveaway_data["participants"].append(user_id)
        await self.update_embed()

        await interaction.response.send_message("✅ You entered the giveaway!", ephemeral=True)

    @discord.ui.button(label="❌ Remove Me", style=discord.ButtonStyle.danger)
    async def remove(self, interaction: discord.Interaction, button: Button):
        user_id = interaction.user.id

        if user_id not in self.giveaway_data["participants"]:
            return await interaction.response.send_message("⚠️ You are not entered!", ephemeral=True)

        self.giveaway_data["participants"].remove(user_id)
        await self.update_embed()

        await interaction.response.send_message("❌ You were removed from the giveaway.", ephemeral=True)


class GiveawayProLive(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_giveaways = {}

    @app_commands.command(
        name="create_giveaway",
        description="Create giveaway (IST → auto timezone)"
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

        # ✅ Parse IST input
        try:
            dt = datetime.strptime(ends_on, "%Y-%m-%d %H:%M").replace(tzinfo=IST)
        except ValueError:
            return await interaction.response.send_message(
                "❌ Invalid format! Use YYYY-MM-DD HH:MM",
                ephemeral=True
            )

        if dt <= datetime.now(IST):
            return await interaction.response.send_message(
                "❌ End time must be in the future.",
                ephemeral=True
            )

        giveaway_data = {
            "title": title,
            "description": description,
            "host": interaction.user,
            "end_time": dt,
            "channel": channel,
            "image": image,
            "participants": []
        }

        self.active_giveaways[channel.id] = giveaway_data

        # ✅ Timestamp
        timestamp = int(dt.astimezone(timezone.utc).timestamp())

        embed = discord.Embed(
            title=f"🎁 {title}",
            description=(
                f"📋 {description}\n\n"
                f"🕒 Ends:\n📅 <t:{timestamp}:F>\n⏰ <t:{timestamp}:R>\n\n"
                f"**Participants:** None yet"
            ),
            color=discord.Color.orange()
        )

        embed.set_footer(
            text=f"Hosted by {interaction.user}",
            icon_url=interaction.user.display_avatar.url
        )

        if image:
            embed.set_image(url=image)

        mention_text = on_create_mentions.mention if on_create_mentions else ""

        message = await channel.send(content=mention_text, embed=embed)

        view = GiveawayView(giveaway_data, message)
        await message.edit(view=view)

        await interaction.response.send_message(
            f"✅ Giveaway created in {channel.mention}",
            ephemeral=True
        )

        # ⏳ Wait until end
        while True:
            now = datetime.now(timezone.utc)
            if now >= dt.astimezone(timezone.utc):
                break
            await asyncio.sleep(30)

        # 🎉 End giveaway
        participants = giveaway_data["participants"]

        if not participants:
            await channel.send(f"❌ Giveaway **{title}** ended. No participants.")
        else:
            winner_id = random.choice(participants)
            await channel.send(f"🎉 Giveaway **{title}** ended! Winner: <@{winner_id}> 🏆")

        del self.active_giveaways[channel.id]


async def setup(bot):
    await bot.add_cog(GiveawayProLive(bot))
