import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta

# ================= CONFIG =================

STAFF_ROLE_ID = 1389824693388837035  # Staff Role ID
LOG_CHANNEL_ID = 1506970182680182805  # Optional moderation logs channel

# ==========================================


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ================= STAFF CHECK =================

    async def interaction_check(self, interaction: discord.Interaction) -> bool:

        if any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
            return True

        await interaction.response.send_message(
            "❌ Only staff members can use moderation commands.",
            ephemeral=True
        )
        return False

    # ================= LOG SYSTEM =================

    async def send_log(self, guild, embed):

        log_channel = guild.get_channel(LOG_CHANNEL_ID)

        if log_channel:
            try:
                await log_channel.send(embed=embed)
            except:
                pass

    # ================= KICK =================

    @app_commands.command(name="kick", description="Kick a member")
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided"
    ):

        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message(
                "❌ You cannot kick this user.",
                ephemeral=True
            )

        await member.kick(reason=reason)

        embed = discord.Embed(
            title="👢 Member Kicked",
            color=discord.Color.orange()
        )

        embed.add_field(name="Member", value=member.mention)
        embed.add_field(name="Moderator", value=interaction.user.mention)
        embed.add_field(name="Reason", value=reason, inline=False)

        await interaction.response.send_message(embed=embed)

        await self.send_log(interaction.guild, embed)

    # ================= BAN =================

    @app_commands.command(name="ban", description="Ban a member")
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided"
    ):

        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message(
                "❌ You cannot ban this user.",
                ephemeral=True
            )

        await member.ban(reason=reason)

        embed = discord.Embed(
            title="⛔ Member Banned",
            color=discord.Color.red()
        )

        embed.add_field(name="Member", value=member.mention)
        embed.add_field(name="Moderator", value=interaction.user.mention)
        embed.add_field(name="Reason", value=reason, inline=False)

        await interaction.response.send_message(embed=embed)

        await self.send_log(interaction.guild, embed)

    # ================= UNBAN =================

    @app_commands.command(name="unban", description="Unban a user")
    async def unban(
        self,
        interaction: discord.Interaction,
        user_id: str
    ):

        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user)

            embed = discord.Embed(
                title="✅ Member Unbanned",
                description=f"{user.mention} was unbanned by {interaction.user.mention}",
                color=discord.Color.green()
            )

            await interaction.response.send_message(embed=embed)

            await self.send_log(interaction.guild, embed)

        except:
            await interaction.response.send_message(
                "❌ Failed to unban user.",
                ephemeral=True
            )

    # ================= TIMEOUT =================

    @app_commands.command(name="timeout", description="Timeout a member")
    async def timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        minutes: int,
        reason: str = "No reason provided"
    ):

        if member.top_role >= interaction.user.top_role:
            return await interaction.response.send_message(
                "❌ You cannot timeout this user.",
                ephemeral=True
            )

        await member.timeout(
            timedelta(minutes=minutes),
            reason=reason
        )

        embed = discord.Embed(
            title="⏱️ Member Timed Out",
            color=discord.Color.yellow()
        )

        embed.add_field(name="Member", value=member.mention)
        embed.add_field(name="Duration", value=f"{minutes} minutes")
        embed.add_field(name="Moderator", value=interaction.user.mention)
        embed.add_field(name="Reason", value=reason, inline=False)

        await interaction.response.send_message(embed=embed)

        await self.send_log(interaction.guild, embed)

    # ================= UNTIMEOUT =================

    @app_commands.command(name="untimeout", description="Remove timeout")
    async def untimeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):

        await member.timeout(None)

        embed = discord.Embed(
            title="✅ Timeout Removed",
            description=f"{member.mention} was unmuted by {interaction.user.mention}",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)

        await self.send_log(interaction.guild, embed)

    # ================= WARN =================

    @app_commands.command(name="warn", description="Warn a member")
    async def warn(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str
    ):

        embed = discord.Embed(
            title="⚠️ Member Warned",
            color=discord.Color.gold()
        )

        embed.add_field(name="Member", value=member.mention)
        embed.add_field(name="Moderator", value=interaction.user.mention)
        embed.add_field(name="Reason", value=reason, inline=False)

        await interaction.response.send_message(embed=embed)

        await self.send_log(interaction.guild, embed)

        try:
            await member.send(
                f"⚠️ You were warned in **{interaction.guild.name}**\nReason: {reason}"
            )
        except:
            pass

    # ================= PURGE =================

    @app_commands.command(name="purge", description="Delete messages")
    async def purge(
        self,
        interaction: discord.Interaction,
        amount: int
    ):

        await interaction.response.defer(ephemeral=True)

        deleted = await interaction.channel.purge(limit=amount)

        embed = discord.Embed(
            title="🧹 Messages Purged",
            description=f"Deleted **{len(deleted)}** messages.",
            color=discord.Color.orange()
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ================= LOCK =================

    @app_commands.command(name="lock", description="Lock a channel")
    async def lock(
        self,
        interaction: discord.Interaction
    ):

        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False

        await interaction.channel.set_permissions(
            interaction.guild.default_role,
            overwrite=overwrite
        )

        embed = discord.Embed(
            description="🔒 Channel locked.",
            color=discord.Color.red()
        )

        await interaction.response.send_message(embed=embed)

    # ================= UNLOCK =================

    @app_commands.command(name="unlock", description="Unlock a channel")
    async def unlock(
        self,
        interaction: discord.Interaction
    ):

        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = True

        await interaction.channel.set_permissions(
            interaction.guild.default_role,
            overwrite=overwrite
        )

        embed = discord.Embed(
            description="🔓 Channel unlocked.",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)

    # ================= SAY =================

    @app_commands.command(name="say", description="Make bot say something")
    async def say(
        self,
        interaction: discord.Interaction,
        message: str
    ):

        await interaction.response.send_message(
            "✅ Message sent.",
            ephemeral=True
        )

        await interaction.channel.send(message)

    # ================= EMBED SAY =================

    @app_commands.command(name="embed", description="Send embed message")
    async def embed(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str
    ):

        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.orange()
        )

        embed.set_footer(
            text=f"Sent by {interaction.user}",
            icon_url=interaction.user.display_avatar.url
        )

        await interaction.response.send_message(
            "✅ Embed sent.",
            ephemeral=True
        )

        await interaction.channel.send(embed=embed)


# ================= SETUP =================

async def setup(bot):
    await bot.add_cog(Moderation(bot))
