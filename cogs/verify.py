import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
import aiohttp
import os

IF_API_KEY = os.getenv("IF_API_KEY")
BASE_URL = "https://api.infiniteflight.com/public/v2"

IFATC_ROLE_ID = 1389833550957641840  # 🔁 replace

verified_users = set()  # simple memory storage


# ================= MODAL =================

class VerifyModal(Modal):
    def __init__(self):
        super().__init__(title="IFC Verification")

        self.username = TextInput(
            label="Infinite Flight Username",
            placeholder="Enter your IFC username...",
            required=True
        )
        self.add_item(self.username)

    async def on_submit(self, interaction: discord.Interaction):

        user_id = interaction.user.id

        # 🔒 Prevent re-verification
        if user_id in verified_users:
            return await interaction.response.send_message(
                "⚠️ You are already verified.",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{BASE_URL}/users?apikey={IF_API_KEY}") as resp:
                    if resp.status != 200:
                        return await interaction.followup.send("❌ API error.")
                    data = await resp.json()
            except Exception as e:
                return await interaction.followup.send(f"❌ Error: {e}")

        users = data.get("result", [])

        user_data = None
        for u in users:
            if u.get("username", "").lower() == self.username.value.lower():
                user_data = u
                break

        if not user_data:
            return await interaction.followup.send("❌ Username not found.")

        # ✅ IFATC check
        if not user_data.get("isAtc", False):
            return await interaction.followup.send(
                "⚠️ You are not an IFATC member."
            )

        role = interaction.guild.get_role(IFATC_ROLE_ID)

        if not role:
            return await interaction.followup.send("❌ Role not found.")

        try:
            await interaction.user.add_roles(role)
        except Exception as e:
            return await interaction.followup.send(f"❌ Role error: {e}")

        # Save verified
        verified_users.add(user_id)

        await interaction.followup.send(
            f"✅ Verified successfully!\n🎖️ IFATC role assigned."
        )


# ================= VIEW =================

class VerifyView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify", emoji="✅", style=discord.ButtonStyle.success, custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(VerifyModal())


# ================= COG =================

class Verify(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="verifypanel", description="Send verification panel")
    async def verifypanel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):

        embed = discord.Embed(
            title="🔐 IFC Verification",
            description=(
                "Verify your Infinite Flight account.\n\n"
                "Click the button below and enter your IFC username.\n\n"
                "🎖️ IFATC members will automatically receive the role."
            ),
            color=discord.Color.orange()
        )

        view = VerifyView()

        await channel.send(embed=embed, view=view)

        await interaction.response.send_message(
            f"✅ Verification panel sent to {channel.mention}",
            ephemeral=True
        )


# ================= SETUP =================

async def setup(bot):
    await bot.add_cog(Verify(bot))
