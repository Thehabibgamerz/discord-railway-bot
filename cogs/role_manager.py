import discord
from discord.ext import commands
from discord import app_commands

# Replace this with your staff role ID
STAFF_ROLE_ID = 1389824693388837035  # Staff role

class RoleManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Helper check: only staff can use
    async def cog_app_command_check(self, interaction: discord.Interaction) -> bool:
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        if staff_role in interaction.user.roles:
            return True
        await interaction.response.send_message("❌ You are not allowed to use this command!", ephemeral=True)
        return False

    @app_commands.command(name="addrole", description="Add a role to a member")
    @app_commands.describe(member="Member to give the role", role="Role to add")
    async def addrole(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        # Prevent giving staff role if you want (optional)
        if role.id == STAFF_ROLE_ID:
            await interaction.response.send_message("❌ You cannot give staff role.", ephemeral=True)
            return

        if role in member.roles:
            await interaction.response.send_message(f"⚠️ {member.display_name} already has the role {role.name}.", ephemeral=True)
            return

        await member.add_roles(role, reason=f"Added by {interaction.user}")
        embed = discord.Embed(
            title="✅ Role Added",
            description=f"{interaction.user.mention} added {role.mention} to {member.mention}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="removerole", description="Remove a role from a member")
    @app_commands.describe(member="Member to remove the role", role="Role to remove")
    async def removerole(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        if role.id == STAFF_ROLE_ID:
            await interaction.response.send_message("❌ You cannot remove staff role.", ephemeral=True)
            return

        if role not in member.roles:
            await interaction.response.send_message(f"⚠️ {member.display_name} does not have the role {role.name}.", ephemeral=True)
            return

        await member.remove_roles(role, reason=f"Removed by {interaction.user}")
        embed = discord.Embed(
            title="⚠️ Role Removed",
            description=f"{interaction.user.mention} removed {role.mention} from {member.mention}",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(RoleManager(bot))
