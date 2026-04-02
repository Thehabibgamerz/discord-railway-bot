import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
from datetime import datetime, timedelta, timezone
import asyncio
import random

IST = timezone(timedelta(hours=5, minutes=30))
STAFF_ROLE_ID = 1389824693388837035


# ================= VIEW =================

class GiveawayView(View):
    def __init__(self, giveaway_data, message):
        super().__init__(timeout=None)
        self.gd = giveaway_data
        self.message = message

    async def update_embed(self):
        timestamp = int(self.gd["end_time"].astimezone(timezone.utc).timestamp())

        participants = [f"<@{uid}>" for uid in self.gd["participants"]]
        participants_text = "\n".join(participants) if participants else "No participants yet"

        req_role = f"<@&{self.gd['required_role']}>" if self.gd["required_role"] else "None"

        embed = discord.Embed(
            title=f"🎁 {self.gd['title']}",
            description=(
                f"📋 {self.gd['description']}\n\n"
                f"🕒 Ends:\n📅 <t:{timestamp}:F>\n⏰ <t:{timestamp}:R>\n\n"
                f"🎯 Winners: **{self.gd['winners']}**\n"
                f"🔒 Required Role: {req_role}\n\n"
                f"**Participants ({len(participants)}):**\n{participants_text}"
            ),
            color=discord.Color.orange()
        )

        embed.set_footer(
            text=f"Hosted by {self.gd['host']}",
            icon_url=self.gd['host'].display_avatar.url
        )

        if self.gd["image"]:
            embed.set_image(url=self.gd["image"])

        await self.message.edit(embed=embed, view=self)

    # 🎉 JOIN
    @discord.ui.button(label="Enter", emoji="🎉", style=discord.ButtonStyle.success)
    async def enter(self, interaction: discord.Interaction, button: Button):

        if self.gd["ended"]:
            return await interaction.response.send_message("❌ Giveaway ended.", ephemeral=True)

        if self.gd["required_role"]:
            role = interaction.guild.get_role(self.gd["required_role"])
            if role not in interaction.user.roles:
                return await interaction.response.send_message("❌ You don't have required role.", ephemeral=True)

        if interaction.user.id in self.gd["participants"]:
            return await interaction.response.send_message("⚠️ Already entered.", ephemeral=True)

        self.gd["participants"].append(interaction.user.id)
        await self.update_embed()
        await interaction.response.send_message("✅ Entered giveaway!", ephemeral=True)

    # ❌ LEAVE
    @discord.ui.button(label="Leave", emoji="❌", style=discord.ButtonStyle.danger)
    async def leave(self, interaction: discord.Interaction, button: Button):

        if interaction.user.id not in self.gd["participants"]:
            return await interaction.response.send_message("⚠️ Not entered.", ephemeral=True)

        self.gd["participants"].remove(interaction.user.id)
        await self.update_embed()
        await interaction.response.send_message("❌ Removed.", ephemeral=True)

    # 🔁 REROLL
    @discord.ui.button(label="Reroll", emoji="🔁", style=discord.ButtonStyle.secondary)
    async def reroll(self, interaction: discord.Interaction, button: Button):

        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("❌ Staff only.", ephemeral=True)

        if not self.gd["participants"]:
            return await interaction.response.send_message("No participants.", ephemeral=True)

        winners = random.sample(
            self.gd["participants"],
            min(self.gd["winners"], len(self.gd["participants"]))
        )

        winner_mentions = " ".join([f"<@{w}>" for w in winners])
        await interaction.response.send_message(f"🔁 New Winners: {winner_mentions}")

    # 🔒 END NOW
    @discord.ui.button(label="End", emoji="⛔", style=discord.ButtonStyle.danger)
    async def end_now(self, interaction: discord.Interaction, button: Button):

        if not any(r.id == STAFF_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("❌ Staff only.", ephemeral=True)

        if self.gd["ended"]:
            return await interaction.response.send_message("Already ended.", ephemeral=True)

        await self.finish_giveaway(interaction.channel)

    async def finish_giveaway(self, channel):
        self.gd["ended"] = True

        participants = self.gd["participants"]

        if not participants:
            await channel.send(f"❌ Giveaway **{self.gd['title']}** ended. No participants.")
            return

        winners = random.sample(
            participants,
            min(self.gd["winners"], len(participants))
        )

        winner_mentions = " ".join([f"<@{w}>" for w in winners])
        await channel.send(f"🎉 Giveaway **{self.gd['title']}** ended!\n🏆 Winners: {winner_mentions}")


# ================= COG =================

class GiveawayPremium(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="giveaway", description="Create premium giveaway")
    async def giveaway(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        ends_on: str,
        winners: int,
        channel: discord.TextChannel,
        required_role: discord.Role = None,
        image: str = None
    ):

        # Parse IST
        try:
            dt = datetime.strptime(ends_on, "%Y-%m-%d %H:%M").replace(tzinfo=IST)
        except:
            return await interaction.response.send_message("❌ Invalid format.", ephemeral=True)

        if dt <= datetime.now(IST):
            return await interaction.response.send_message("❌ Must be future time.", ephemeral=True)

        giveaway_data = {
            "title": title,
            "description": description,
            "host": interaction.user,
            "end_time": dt,
            "participants": [],
            "winners": winners,
            "required_role": required_role.id if required_role else None,
            "image": image,
            "ended": False
        }

        timestamp = int(dt.astimezone(timezone.utc).timestamp())

        embed = discord.Embed(
            title=f"🎁 {title}",
            description=(
                f"📋 {description}\n\n"
                f"🕒 Ends:\n📅 <t:{timestamp}:F>\n⏰ <t:{timestamp}:R>\n\n"
                f"🎯 Winners: **{winners}**\n"
                f"🔒 Required Role: {required_role.mention if required_role else 'None'}\n\n"
                f"**Participants:** None yet"
            ),
            color=discord.Color.orange()
        )

        embed.set_footer(text=f"Hosted by {interaction.user}", icon_url=interaction.user.display_avatar.url)

        if image:
            embed.set_image(url=image)

        msg = await channel.send(embed=embed)

        view = GiveawayView(giveaway_data, msg)
        await msg.edit(view=view)

        await interaction.response.send_message(f"✅ Giveaway created in {channel.mention}", ephemeral=True)

        # Auto end
        while True:
            if datetime.now(timezone.utc) >= dt.astimezone(timezone.utc):
                break
            await asyncio.sleep(30)

        await view.finish_giveaway(channel)


async def setup(bot):
    await bot.add_cog(GiveawayPremium(bot))
