import discord
from discord.ext import commands
from discord import app_commands
from datetime import timedelta, datetime, timezone
import sqlite3
import os

# ================= CONFIG =================

STAFF_ROLE_ID = 1389824693388837035  # Staff Role ID
LOG_CHANNEL_ID = 1506970182680182805  # Optional moderation logs channel

MAX_TIMEOUT_MINUTES = 40320  # Discord's hard cap: 28 days
MAX_PURGE_AMOUNT = 100  # Discord's bulk-delete cap per call

DB_PATH = os.path.join(os.path.dirname(__file__), "moderation.db")

# Same caveat as elsewhere: if your host's filesystem is ephemeral (e.g.
# Railway without a mounted volume), this file resets on every redeploy.

# ==========================================


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            warning_id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def db_add_warning(guild_id, user_id, moderator_id, reason):
    conn = get_db()
    conn.execute(
        "INSERT INTO warnings (guild_id, user_id, moderator_id, reason, created_at) VALUES (?, ?, ?, ?, ?)",
        (guild_id, user_id, moderator_id, reason, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()


def db_get_warnings(guild_id, user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC",
        (guild_id, user_id)
    ).fetchall()
    conn.close()
    return rows


# Mentions are allowed for specific users/roles a moderator targets on
# purpose, but @everyone/@here are blocked to prevent /say or /embed
# being used to mass-ping the server.
SAFE_MENTIONS = discord.AllowedMentions(everyone=False, here=False, roles=True, users=True)


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        init_db()

    # ================= STAFF CHECK =================
    # NOTE: the correct hook for cog-wide app command checks is
    # `cog_app_command_check`, not `interaction_check` (which only applies
    # to discord.ui.View / app_commands.Group, not Cog). The previous
    # version of this file used the wrong method name, so the staff check
    # silently never ran and every command here was usable by anyone.

    async def cog_app_command_check(self, interaction: discord.Interaction) -> bool:
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
            except discord.HTTPException:
                pass

    # ================= HIERARCHY HELPERS =================

    def can_moderate(self, interaction: discord.Interaction, member: discord.Member) -> str | None:
        """Returns an error message string if the action should be blocked, else None."""

        if member.id == interaction.user.id:
            return "❌ You cannot target yourself."

        if member.id == self.bot.user.id:
            return "❌ You cannot target me."

        # Server owner bypasses role-hierarchy checks (their top_role can be
        # @everyone if they have no extra roles assigned, which would
        # otherwise incorrectly block them)
        if interaction.user.id != interaction.guild.owner_id:
            if member.top_role >= interaction.user.top_role:
                return "❌ You cannot moderate this user (equal or higher role)."

        if member.top_role >= interaction.guild.me.top_role:
            return "❌ I cannot moderate this user — their role is equal to or higher than mine."

        return None

    # ================= KICK =================

    @app_commands.command(name="kick", description="Kick a member")
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided"
    ):
        error = self.can_moderate(interaction, member)
        if error:
            return await interaction.response.send_message(error, ephemeral=True)

        try:
            await member.kick(reason=reason)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to kick this member.", ephemeral=True
            )
        except discord.HTTPException as e:
            return await interaction.response.send_message(f"❌ Failed to kick: {e}", ephemeral=True)

        embed = discord.Embed(title="👢 Member Kicked", color=discord.Color.orange())
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
        error = self.can_moderate(interaction, member)
        if error:
            return await interaction.response.send_message(error, ephemeral=True)

        try:
            await member.ban(reason=reason)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to ban this member.", ephemeral=True
            )
        except discord.HTTPException as e:
            return await interaction.response.send_message(f"❌ Failed to ban: {e}", ephemeral=True)

        embed = discord.Embed(title="⛔ Member Banned", color=discord.Color.red())
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
        if not user_id.isdigit():
            return await interaction.response.send_message(
                "❌ That doesn't look like a valid user ID.", ephemeral=True
            )

        try:
            user = await self.bot.fetch_user(int(user_id))
        except discord.NotFound:
            return await interaction.response.send_message("❌ No user found with that ID.", ephemeral=True)
        except discord.HTTPException as e:
            return await interaction.response.send_message(f"❌ Error fetching user: {e}", ephemeral=True)

        try:
            await interaction.guild.unban(user)
        except discord.NotFound:
            return await interaction.response.send_message("❌ That user is not banned.", ephemeral=True)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to unban users.", ephemeral=True
            )
        except discord.HTTPException as e:
            return await interaction.response.send_message(f"❌ Failed to unban: {e}", ephemeral=True)

        embed = discord.Embed(
            title="✅ Member Unbanned",
            description=f"{user.mention} was unbanned by {interaction.user.mention}",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)
        await self.send_log(interaction.guild, embed)

    # ================= TIMEOUT =================

    @app_commands.command(name="timeout", description="Timeout a member")
    async def timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        minutes: int,
        reason: str = "No reason provided"
    ):
        error = self.can_moderate(interaction, member)
        if error:
            return await interaction.response.send_message(error, ephemeral=True)

        if minutes <= 0 or minutes > MAX_TIMEOUT_MINUTES:
            return await interaction.response.send_message(
                f"❌ Minutes must be between 1 and {MAX_TIMEOUT_MINUTES} (28 days).", ephemeral=True
            )

        try:
            await member.timeout(timedelta(minutes=minutes), reason=reason)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to timeout this member.", ephemeral=True
            )
        except discord.HTTPException as e:
            return await interaction.response.send_message(f"❌ Failed to timeout: {e}", ephemeral=True)

        embed = discord.Embed(title="⏱️ Member Timed Out", color=discord.Color.gold())
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
        try:
            await member.timeout(None)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to remove this timeout.", ephemeral=True
            )
        except discord.HTTPException as e:
            return await interaction.response.send_message(f"❌ Failed: {e}", ephemeral=True)

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
        db_add_warning(interaction.guild.id, member.id, interaction.user.id, reason)
        warning_count = len(db_get_warnings(interaction.guild.id, member.id))

        embed = discord.Embed(title="⚠️ Member Warned", color=discord.Color.gold())
        embed.add_field(name="Member", value=member.mention)
        embed.add_field(name="Moderator", value=interaction.user.mention)
        embed.add_field(name="Total Warnings", value=str(warning_count))
        embed.add_field(name="Reason", value=reason, inline=False)

        await interaction.response.send_message(embed=embed)
        await self.send_log(interaction.guild, embed)

        try:
            await member.send(
                f"⚠️ You were warned in **{interaction.guild.name}**\nReason: {reason}"
            )
        except discord.Forbidden:
            pass  # User has DMs closed — not an error worth surfacing

    # ================= WARNINGS (list) =================

    @app_commands.command(name="warnings", description="View a member's warning history")
    async def warnings(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):
        rows = db_get_warnings(interaction.guild.id, member.id)

        if not rows:
            return await interaction.response.send_message(
                f"{member.mention} has no warnings.", ephemeral=True
            )

        embed = discord.Embed(
            title=f"⚠️ Warnings for {member.display_name}",
            description=f"Total: **{len(rows)}**",
            color=discord.Color.gold()
        )

        for row in rows[:10]:
            mod = interaction.guild.get_member(row["moderator_id"])
            mod_name = mod.mention if mod else f"<@{row['moderator_id']}>"
            created = row["created_at"][:10]  # just the date
            embed.add_field(
                name=f"#{row['warning_id']} — {created}",
                value=f"By {mod_name}: {row['reason']}",
                inline=False
            )

        if len(rows) > 10:
            embed.set_footer(text=f"Showing 10 most recent of {len(rows)} warnings.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ================= PURGE =================

    @app_commands.command(name="purge", description="Delete messages")
    async def purge(
        self,
        interaction: discord.Interaction,
        amount: int
    ):
        if amount <= 0 or amount > MAX_PURGE_AMOUNT:
            return await interaction.response.send_message(
                f"❌ Amount must be between 1 and {MAX_PURGE_AMOUNT}.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        try:
            deleted = await interaction.channel.purge(limit=amount)
        except discord.Forbidden:
            return await interaction.followup.send(
                "❌ I don't have permission to delete messages here.", ephemeral=True
            )
        except discord.HTTPException as e:
            return await interaction.followup.send(f"❌ Failed to purge: {e}", ephemeral=True)

        embed = discord.Embed(
            title="🧹 Messages Purged",
            description=f"Deleted **{len(deleted)}** messages.",
            color=discord.Color.orange()
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ================= LOCK =================

    @app_commands.command(name="lock", description="Lock a channel")
    async def lock(self, interaction: discord.Interaction):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False

        try:
            await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to edit this channel's permissions.", ephemeral=True
            )

        embed = discord.Embed(description="🔒 Channel locked.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)

    # ================= UNLOCK =================

    @app_commands.command(name="unlock", description="Unlock a channel")
    async def unlock(self, interaction: discord.Interaction):
        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = True

        try:
            await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to edit this channel's permissions.", ephemeral=True
            )

        embed = discord.Embed(description="🔓 Channel unlocked.", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)

    # ================= SAY =================

    @app_commands.command(name="say", description="Make bot say something")
    async def say(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message("✅ Message sent.", ephemeral=True)
        await interaction.channel.send(message, allowed_mentions=SAFE_MENTIONS)

    # ================= EMBED SAY =================

    @app_commands.command(name="embed", description="Send embed message")
    async def embed(self, interaction: discord.Interaction, title: str, description: str):
        embed = discord.Embed(title=title, description=description, color=discord.Color.orange())
        embed.set_footer(
            text=f"Sent by {interaction.user}",
            icon_url=interaction.user.display_avatar.url
        )

        await interaction.response.send_message("✅ Embed sent.", ephemeral=True)
        await interaction.channel.send(embed=embed, allowed_mentions=SAFE_MENTIONS)


# ================= SETUP =================

async def setup(bot):
    await bot.add_cog(Moderation(bot))
