import discord
from discord.ext import commands
from discord import app_commands
import json
import os

DATA_FILE = "callsigns.json"


# ================= DATA =================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


# ================= COG =================

class Callsign(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 🔍 CHECK CALLSIGN
    @app_commands.command(name="check_callsign", description="Check if a callsign is available")
    async def check_callsign(self, interaction: discord.Interaction, number: int):

        if number < 1 or number > 999:
            return await interaction.response.send_message("❌ Use number between 1–999", ephemeral=True)

        callsign = f"{number:03}QP"
        data = load_data()

        owner = data.get(callsign)

        embed = discord.Embed(color=discord.Color.orange())

        if owner:
            embed.title = "❌ Callsign Unavailable"
            embed.description = f"✈️ **{callsign}** is already taken.\n👤 Owner: <@{owner}>"
        else:
            embed.title = "✅ Callsign Available"
            embed.description = f"✈️ **{callsign}** is available!"

        await interaction.response.send_message(embed=embed)

    # 🎟️ CLAIM
    @app_commands.command(name="claim_callsign", description="Claim a callsign")
    async def claim_callsign(self, interaction: discord.Interaction, number: int):

        if number < 1 or number > 999:
            return await interaction.response.send_message("❌ Use 1–999", ephemeral=True)

        callsign = f"{number:03}QP"
        data = load_data()

        # Check if already taken
        if callsign in data:
            return await interaction.response.send_message("❌ Callsign already taken.", ephemeral=True)

        # Check if user already has one
        for cs, uid in data.items():
            if uid == interaction.user.id:
                return await interaction.response.send_message(
                    f"⚠️ You already own **{cs}**",
                    ephemeral=True
                )

        # Assign
        data[callsign] = interaction.user.id
        save_data(data)

        embed = discord.Embed(
            title="🎉 Callsign Assigned",
            description=f"You now own ✈️ **{callsign}**",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)

    # ❌ RELEASE
    @app_commands.command(name="release_callsign", description="Release your callsign")
    async def release_callsign(self, interaction: discord.Interaction):

        data = load_data()

        for cs, uid in list(data.items()):
            if uid == interaction.user.id:
                del data[cs]
                save_data(data)

                return await interaction.response.send_message(
                    f"❌ Released **{cs}**"
                )

        await interaction.response.send_message("⚠️ You don't have a callsign.", ephemeral=True)

    # 👤 MY CALLSIGN
    @app_commands.command(name="my_callsign", description="View your callsign")
    async def my_callsign(self, interaction: discord.Interaction):

        data = load_data()

        for cs, uid in data.items():
            if uid == interaction.user.id:
                return await interaction.response.send_message(
                    f"✈️ Your callsign: **{cs}**"
                )

        await interaction.response.send_message("⚠️ You don't have a callsign.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Callsign(bot))
