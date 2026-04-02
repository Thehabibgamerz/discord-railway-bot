import discord
from discord.ext import commands
from discord import app_commands
import json
import os

DATA_FILE = "callsigns.json"
STAFF_ROLE_ID = 1389824693388837035  # 🔁 your staff role ID


# ================= DATA =================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


def is_staff(member: discord.Member):
    return any(role.id == STAFF_ROLE_ID for role in member.roles)


# ================= COG =================

class Callsign(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 🔍 CHECK CALLSIGN
    @app_commands.command(name="check_callsign", description="Check callsign availability")
    async def check_callsign(self, interaction: discord.Interaction, number: int):

        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Staff only", ephemeral=True)

        if number < 100 or number > 999:
            return await interaction.response.send_message("❌ Use 100–999", ephemeral=True)

        callsign = f"{number}QP"
        data = load_data()

        if callsign in data:
            await interaction.response.send_message(
                f"❌ {callsign} is TAKEN (User: <@{data[callsign]}>)"
            )
        else:
            await interaction.response.send_message(
                f"✅ {callsign} is AVAILABLE"
            )

    # 📋 FULL LIST
    @app_commands.command(name="callsign_list", description="Show all callsigns (100–999)")
    async def callsign_list(self, interaction: discord.Interaction):

        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Staff only", ephemeral=True)

        data = load_data()

        lines = []
        for i in range(100, 1000):
            cs = f"{i}QP"
            if cs in data:
                lines.append(f"{cs} - TAKEN")
            else:
                lines.append(f"{cs} - AVAILABLE")

        # Discord limit fix (split messages)
        chunk_size = 50
        chunks = [lines[i:i+chunk_size] for i in range(0, len(lines), chunk_size)]

        await interaction.response.send_message("📋 Callsign List (Part 1)")

        for idx, chunk in enumerate(chunks):
            text = "\n".join(chunk)
            await interaction.followup.send(f"**Part {idx+1}:**\n{text}")


async def setup(bot):
    await bot.add_cog(Callsign(bot))
