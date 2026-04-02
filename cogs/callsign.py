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
        with open(DATA_FILE, "w") as f:
            f.write("{}")
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


def is_staff(member):
    return any(role.id == STAFF_ROLE_ID for role in member.roles)


# ================= COG =================

class Callsign(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 🔍 CHECK CALLSIGN
    @app_commands.command(name="check_callsign")
    async def check_callsign(self, interaction: discord.Interaction, number: int):

        if number < 100 or number > 999:
            return await interaction.response.send_message("❌ Use 100–999", ephemeral=True)

        cs = f"{number}QP"
        data = load_data()

        if cs in data:
            await interaction.response.send_message(f"❌ {cs} is TAKEN (<@{data[cs]}>)")
        else:
            await interaction.response.send_message(f"✅ {cs} is AVAILABLE")

    # 📋 CALLSIGN LIST (WITH RANGE)
    @app_commands.command(name="callsign_list")
    async def callsign_list(
        self,
        interaction: discord.Interaction,
        start: int,
        end: int
    ):

        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Staff only", ephemeral=True)

        if start < 100 or end > 999 or start > end:
            return await interaction.response.send_message("❌ Use valid range (100–999)", ephemeral=True)

        data = load_data()
        lines = []

        for i in range(start, end + 1):
            cs = f"{i}QP"
            status = "TAKEN" if cs in data else "AVAILABLE"
            lines.append(f"{cs} - {status}")

        # Split messages
        chunks = [lines[i:i+50] for i in range(0, len(lines), 50)]

        await interaction.response.send_message(f"📋 Callsigns {start}-{end}")

        for idx, chunk in enumerate(chunks):
            await interaction.followup.send(f"Part {idx+1}:\n" + "\n".join(chunk))

    # 🛠️ ASSIGN CALLSIGN
    @app_commands.command(name="assign_callsign")
    async def assign_callsign(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        number: int
    ):

        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Staff only", ephemeral=True)

        if number < 100 or number > 999:
            return await interaction.response.send_message("❌ Use 100–999", ephemeral=True)

        cs = f"{number}QP"
        data = load_data()

        if cs in data:
            return await interaction.response.send_message(f"❌ {cs} already taken")

        for k, v in data.items():
            if v == member.id:
                return await interaction.response.send_message(f"⚠️ {member.mention} already has {k}")

        # Save
        data[cs] = member.id
        save_data(data)

        # Update nickname
        try:
            await member.edit(nick=f"{member.name} | {cs}")
        except Exception as e:
            print(f"Nickname error: {e}")

        await interaction.response.send_message(f"✅ Assigned {cs} to {member.mention}")

    # ❌ REMOVE CALLSIGN
    @app_commands.command(name="remove_callsign")
    async def remove_callsign(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):

        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Staff only", ephemeral=True)

        data = load_data()

        for cs, uid in list(data.items()):
            if uid == member.id:
                del data[cs]
                save_data(data)

                # Reset nickname
                try:
                    await member.edit(nick=None)
                except Exception as e:
                    print(f"Nickname reset error: {e}")

                return await interaction.response.send_message(
                    f"❌ Removed {cs} from {member.mention}"
                )

        await interaction.response.send_message(f"⚠️ {member.mention} has no callsign")


async def setup(bot):
    await bot.add_cog(Callsign(bot))
