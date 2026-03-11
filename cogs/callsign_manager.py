import discord
from discord.ext import commands
from discord import app_commands

STAFF_ROLE = 1389824693388837035

# Stored airline prefixes
tracked_callsigns = ["Akasa Air"]


class CallsignManager(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # Add callsign
    @app_commands.command(name="addcallsign", description="Add airline callsign prefix")
    async def addcallsign(self, interaction: discord.Interaction, prefix: str):

        if STAFF_ROLE not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message(
                "❌ Only staff can add callsigns.", ephemeral=True
            )
            return

        if prefix in tracked_callsigns:
            await interaction.response.send_message(
                "⚠️ This callsign already exists.", ephemeral=True
            )
            return

        tracked_callsigns.append(prefix)

        embed = discord.Embed(
            title="✅ Callsign Added",
            description=f"Flights starting with **{prefix}** will now be tracked.",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)

    # Remove callsign
    @app_commands.command(name="removecallsign", description="Remove airline callsign")
    async def removecallsign(self, interaction: discord.Interaction, prefix: str):

        if STAFF_ROLE not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message(
                "❌ Only staff can remove callsigns.", ephemeral=True
            )
            return

        if prefix not in tracked_callsigns:
            await interaction.response.send_message(
                "⚠️ Callsign not found.", ephemeral=True
            )
            return

        tracked_callsigns.remove(prefix)

        embed = discord.Embed(
            title="🗑️ Callsign Removed",
            description=f"Stopped tracking **{prefix}** flights.",
            color=discord.Color.red()
        )

        await interaction.response.send_message(embed=embed)

    # List callsigns
    @app_commands.command(name="callsigns", description="View tracked airline callsigns")
    async def callsigns(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="✈️ Tracked Airline Callsigns",
            description="\n".join(tracked_callsigns),
            color=discord.Color.orange()
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(CallsignManager(bot))
