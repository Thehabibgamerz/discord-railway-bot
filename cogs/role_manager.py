import discord
from discord.ext import commands
from discord import app_commands

# ================= CONFIG =================

STAFF_ROLE_ID = 1389824693388837035
LOG_CHANNEL_ID = 1506970182680182805  # Optional logs channel

# ==========================================


class RoleManager(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # ================= STAFF CHECK =================

    async def interaction_check(self, interaction: discord.Interaction):

        if any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
            return True

        await interaction.response.send_message(
            "❌ Only staff members can use this command.",
            ephemeral=True
        )
        return False

    # ================= LOGS =================

    async def send_log(self, guild, message):

        log_channel = guild.get_channel(LOG_CHANNEL_ID)

        if log_channel:
            try:
                await log_channel.send(message)
            except:
                pass

    # ================= ADD ROLE =================

    @app_commands.command(
        name="addrole",
        description="Add a role to a member"
    )
    async def addrole(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role
    ):

        # Prevent staff role edit
        if role.id == STAFF_ROLE_ID:
            return await interaction.response.send_message(
                "❌ You cannot manage the staff role.",
                ephemeral=True
            )

        # Already has role
        if role in member.roles:
            return await interaction.response.send_message(
                f"⚠️ {member.mention} already has {role.name}",
                ephemeral=True
            )

        # Role hierarchy check
        if role >= interaction.user.top_role:
            return await interaction.response.send_message(
                "❌ You cannot assign a role higher or equal to yours.",
                ephemeral=True
            )

        try:
            await member.add_roles(
                role,
                reason=f"Added by {interaction.user}"
            )

            msg = (
                f"✅ {interaction.user.mention} added "
                f"{role.mention} to {member.mention}"
            )

            await interaction.response.send_message(msg)

            await self.send_log(interaction.guild, msg)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to add role.\n{e}",
                ephemeral=True
            )

    # ================= REMOVE ROLE =================

    @app_commands.command(
        name="removerole",
        description="Remove a role from a member"
    )
    async def removerole(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role
    ):

        # Prevent staff role edit
        if role.id == STAFF_ROLE_ID:
            return await interaction.response.send_message(
                "❌ You cannot manage the staff role.",
                ephemeral=True
            )

        # Member doesn't have role
        if role not in member.roles:
            return await interaction.response.send_message(
                f"⚠️ {member.mention} does not have {role.name}",
                ephemeral=True
            )

        # Role hierarchy check
        if role >= interaction.user.top_role:
            return await interaction.response.send_message(
                "❌ You cannot remove a role higher or equal to yours.",
                ephemeral=True
            )

        try:
            await member.remove_roles(
                role,
                reason=f"Removed by {interaction.user}"
            )

            msg = (
                f"❌ {interaction.user.mention} removed "
                f"{role.mention} from {member.mention}"
            )

            await interaction.response.send_message(msg)

            await self.send_log(interaction.guild, msg)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to remove role.\n{e}",
                ephemeral=True
            )

    # ================= ROLE INFO =================

    @app_commands.command(
        name="roleinfo",
        description="Get role information"
    )
    async def roleinfo(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):

        perms = []

        important_perms = {
            "administrator": "Administrator",
            "manage_guild": "Manage Server",
            "manage_roles": "Manage Roles",
            "manage_channels": "Manage Channels",
            "kick_members": "Kick Members",
            "ban_members": "Ban Members",
            "mention_everyone": "Mention Everyone"
        }

        for perm, name in important_perms.items():
            if getattr(role.permissions, perm):
                perms.append(name)

        perms_text = ", ".join(perms) if perms else "No major permissions"

        msg = (
            f"📌 Role Info: {role.mention}\n\n"
            f"• Name: {role.name}\n"
            f"• ID: {role.id}\n"
            f"• Members: {len(role.members)}\n"
            f"• Position: {role.position}\n"
            f"• Color: {role.color}\n"
            f"• Mentionable: {role.mentionable}\n"
            f"• Hoisted: {role.hoist}\n\n"
            f"🔑 Permissions:\n{perms_text}"
        )

        await interaction.response.send_message(msg)

    # ================= ROLE MEMBERS =================

    @app_commands.command(
        name="rolemembers",
        description="View members with a role"
    )
    async def rolemembers(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):

        if not role.members:
            return await interaction.response.send_message(
                "❌ No members have this role."
            )

        members = [member.mention for member in role.members]

        chunks = [
            members[i:i+30]
            for i in range(0, len(members), 30)
        ]

        await interaction.response.send_message(
            f"📋 Members with {role.mention}"
        )

        for chunk in chunks:
            await interaction.followup.send("\n".join(chunk))

    # ================= ROLE ALL =================

    @app_commands.command(
        name="roleall",
        description="Add a role to everyone"
    )
    async def roleall(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):

        await interaction.response.send_message(
            f"⏳ Adding {role.mention} to everyone...",
            ephemeral=True
        )

        count = 0

        for member in interaction.guild.members:

            if role not in member.roles and not member.bot:
                try:
                    await member.add_roles(role)
                    count += 1
                except:
                    pass

        await interaction.followup.send(
            f"✅ Added {role.mention} to {count} members."
        )

    # ================= REMOVEROLE ALL =================

    @app_commands.command(
        name="removeroleall",
        description="Remove a role from everyone"
    )
    async def removeroleall(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):

        await interaction.response.send_message(
            f"⏳ Removing {role.mention} from everyone...",
            ephemeral=True
        )

        count = 0

        for member in interaction.guild.members:

            if role in member.roles:
                try:
                    await member.remove_roles(role)
                    count += 1
                except:
                    pass

        await interaction.followup.send(
            f"✅ Removed {role.mention} from {count} members."
        )


# ================= SETUP =================

async def setup(bot):
    await bot.add_cog(RoleManager(bot))
