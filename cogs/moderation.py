import discord
from discord.ext import commands
from discord import app_commands

# Replace with your staff role ID
STAFF_ROLE_ID = 1389824693388837035  # Staff

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Staff-only check
    async def cog_app_command_check(self, interaction: discord.Interaction) -> bool:
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        if staff_role in interaction.user.roles:
            return True
        await interaction.response.send_message("❌ You are not allowed to use this command!", ephemeral=True)
        return False

    # Kick command
    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.describe(member="Member to kick", reason="Reason for kick")
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        await member.kick(reason=reason)
        embed = discord.Embed(
            title="👢 Member Kicked",
            description=f"{member.mention} was kicked by {interaction.user.mention}\n**Reason:** {reason}",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)

    # Ban command
    @app_commands.command(name="ban", description="Ban a member from the server")
    @app_commands.describe(member="Member to ban", reason="Reason for ban")
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        await member.ban(reason=reason)
        embed = discord.Embed(
            title="⛔ Member Banned",
            description=f"{member.mention} was banned by {interaction.user.mention}\n**Reason:** {reason}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

    # Timeout command
    @app_commands.command(name="timeout", description="Timeout a member")
    @app_commands.describe(member="Member to timeout", duration="Duration in minutes", reason="Reason for timeout")
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = "No reason provided"):
        await member.timeout_for(duration * 60, reason=reason)  # duration in seconds
        embed = discord.Embed(
            title="⏱️ Member Timed Out",
            description=f"{member.mention} was timed out for **{duration} minutes** by {interaction.user.mention}\n**Reason:** {reason}",
            color=discord.Color.yellow()
        )
        await interaction.response.send_message(embed=embed)

    # Remove timeout
    @app_commands.command(name="untimeout", description="Remove timeout from a member")
    @app_commands.describe(member="Member to remove timeout")
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member):
        await member.remove_timeout()
        embed = discord.Embed(
            title="✅ Timeout Removed",
            description=f"Timeout removed for {member.mention} by {interaction.user.mention}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    # Say command
    @app_commands.command(name="say", description="Bot says a message")
    @app_commands.describe(message="Message for the bot to say")
    async def say(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message(message)

async def setup(bot):
    await bot.add_cog(Moderation(bot))
