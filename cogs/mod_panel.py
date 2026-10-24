
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput, Select
from datetime import timedelta, datetime, timezone


# =========================================================
# CONFIGURATION
# =========================================================

STAFF_ROLE_ID = 1389824693388837035
EXEC_ROLE_ID = 1389824452778262589
LOG_CHANNEL_ID = 1506970182680182805

MAX_TIMEOUT_MINUTES = 40320  # 28 days
PANEL_TIMEOUT = 180


# =========================================================
# PERMISSIONS AND VALIDATION
# =========================================================

def is_authorized(member: discord.Member) -> bool:
    return any(
        role.id in (STAFF_ROLE_ID, EXEC_ROLE_ID)
        for role in member.roles
    )


def can_moderate(
    moderator: discord.Member,
    target: discord.Member,
    guild: discord.Guild,
) -> str | None:

    bot_member = guild.me

    if bot_member is None:
        return "❌ I could not verify my server permissions."

    if target.id == moderator.id:
        return "❌ You cannot moderate yourself."

    if target.id == bot_member.id:
        return "❌ You cannot moderate the bot."

    if target.id == guild.owner_id:
        return "❌ The server owner cannot be moderated by this panel."

    if moderator.id != guild.owner_id:
        if target.top_role >= moderator.top_role:
            return (
                "❌ You cannot moderate this member because "
                "their highest role is equal to or higher than yours."
            )

    if target.top_role >= bot_member.top_role:
        return (
            "❌ I cannot moderate this member because their "
            "highest role is equal to or higher than my highest role."
        )

    return None


def bot_has_permission(
    guild: discord.Guild,
    permission: str,
) -> bool:
    bot_member = guild.me

    if bot_member is None:
        return False

    return getattr(bot_member.guild_permissions, permission, False)


# =========================================================
# LOGGING
# =========================================================

async def send_log(
    guild: discord.Guild,
    embed: discord.Embed,
):
    channel = guild.get_channel(LOG_CHANNEL_ID)

    if channel is None:
        try:
            channel = await guild.fetch_channel(LOG_CHANNEL_ID)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return

    if not hasattr(channel, "send"):
        return

    try:
        await channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        pass


def make_log_embed(
    action: str,
    color: discord.Color,
    moderator: discord.Member,
    target: discord.abc.User,
    reason: str,
    extra: str | None = None,
) -> discord.Embed:

    embed = discord.Embed(
        title=f"🛡️ {action}",
        color=color,
        timestamp=datetime.now(timezone.utc),
    )

    embed.add_field(
        name="👤 Member",
        value=f"{target.mention}\n`{target.id}`",
        inline=True,
    )

    embed.add_field(
        name="🎭 Moderator",
        value=f"{moderator.mention}\n`{moderator.id}`",
        inline=True,
    )

    embed.add_field(
        name="📋 Reason",
        value=reason[:1024] if reason else "No reason provided",
        inline=False,
    )

    if extra:
        embed.add_field(
            name="ℹ️ Details",
            value=extra[:1024],
            inline=False,
        )

    embed.set_thumbnail(url=target.display_avatar.url)
    embed.set_footer(text="Akasa Air Virtual • Moderation Logs")

    return embed


# =========================================================
# INTERACTION HELPERS
# =========================================================

async def respond_error(
    interaction: discord.Interaction,
    message: str,
):
    """Respond safely whether the interaction was already acknowledged."""

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(
            message,
            ephemeral=True,
        )


async def recheck_permissions(
    interaction: discord.Interaction,
    target: discord.Member,
) -> bool:
    """Revalidate authorization when a button or modal is used."""

    if not interaction.guild or not isinstance(
        interaction.user, discord.Member
    ):
        await respond_error(interaction, "❌ This action must be used in a server.")
        return False

    if not is_authorized(interaction.user):
        await respond_error(
            interaction,
            "❌ You need the Staff or Executive Team role to use this panel.",
        )
        return False

    error = can_moderate(interaction.user, target, interaction.guild)

    if error:
        await respond_error(interaction, error)
        return False

    return True


# =========================================================
# REASON MODAL
# =========================================================

class ReasonModal(Modal):

    def __init__(
        self,
        action: str,
        target: discord.Member,
        extra_field: str | None = None,
    ):
        super().__init__(
            title=f"{action} — {target.display_name}"[:45]
        )

        self.action = action
        self.target = target

        self.reason = TextInput(
            label="Reason",
            placeholder="Enter the reason for this action",
            required=True,
            min_length=1,
            max_length=500,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.reason)

        self.extra_input = None

        if extra_field:
            self.extra_input = TextInput(
                label=extra_field,
                placeholder="Enter duration in minutes",
                required=True,
                min_length=1,
                max_length=5,
            )
            self.add_item(self.extra_input)

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):
        if not await recheck_permissions(interaction, self.target):
            return

        guild = interaction.guild
        moderator = interaction.user
        target = self.target
        reason = self.reason.value.strip()

        if not reason:
            return await respond_error(
                interaction,
                "❌ Please provide a reason.",
            )

        if not guild or not isinstance(moderator, discord.Member):
            return await respond_error(
                interaction,
                "❌ This action must be used inside a server.",
            )

        # Validate action-specific bot permissions before acting.
        required_permissions = {
            "Kick": "kick_members",
            "Ban": "ban_members",
            "Softban": "ban_members",
            "Timeout": "moderate_members",
            "Remove Timeout": "moderate_members",
        }

        permission_name = required_permissions.get(self.action)

        if permission_name and not bot_has_permission(
            guild, permission_name
        ):
            return await respond_error(
                interaction,
                f"❌ I need the `{permission_name}` permission.",
            )

        # Acknowledge before performing a potentially slow API request.
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            if self.action == "Warn":
                log = make_log_embed(
                    "Member Warned",
                    discord.Color.gold(),
                    moderator,
                    target,
                    reason,
                )

                dm_sent = True

                try:
                    await target.send(
                        f"⚠️ **You have received a warning in {guild.name}.**\n"
                        f"Reason: {reason}"
                    )
                except (discord.Forbidden, discord.HTTPException):
                    dm_sent = False

                await send_log(guild, log)

                message = (
                    f"⚠️ {target.mention} has been warned."
                    if dm_sent
                    else (
                        f"⚠️ {target.mention} has been warned, "
                        "but I could not deliver the DM."
                    )
                )

            elif self.action == "Timeout":
                try:
                    minutes = int(
                        self.extra_input.value.strip()
                        if self.extra_input
                        else "60"
                    )
                except ValueError:
                    return await interaction.followup.send(
                        "❌ Duration must be a whole number of minutes.",
                        ephemeral=True,
                    )

                if not 1 <= minutes <= MAX_TIMEOUT_MINUTES:
                    return await interaction.followup.send(
                        f"❌ Duration must be between 1 and "
                        f"{MAX_TIMEOUT_MINUTES} minutes.",
                        ephemeral=True,
                    )

                await target.timeout(
                    timedelta(minutes=minutes),
                    reason=f"{reason} | Moderator: {moderator} ({moderator.id})",
                )

                log = make_log_embed(
                    "Member Timed Out",
                    discord.Color.yellow(),
                    moderator,
                    target,
                    reason,
                    extra=f"Duration: {minutes} minutes",
                )

                await send_log(guild, log)

                message = (
                    f"⏱️ {target.mention} has been timed out "
                    f"for **{minutes} minutes**."
                )

            elif self.action == "Remove Timeout":
                await target.timeout(
                    None,
                    reason=f"{reason} | Moderator: {moderator} ({moderator.id})",
                )

                log = make_log_embed(
                    "Timeout Removed",
                    discord.Color.green(),
                    moderator,
                    target,
                    reason,
                )

                await send_log(guild, log)
                message = f"✅ Timeout removed from {target.mention}."

            elif self.action == "Kick":
                await target.kick(
                    reason=f"{reason} | Moderator: {moderator} ({moderator.id})"
                )

                log = make_log_embed(
                    "Member Kicked",
                    discord.Color.orange(),
                    moderator,
                    target,
                    reason,
                )

                await send_log(guild, log)
                message = f"👢 **{target.display_name}** has been kicked."

            elif self.action == "Ban":
                await target.ban(
                    reason=f"{reason} | Moderator: {moderator} ({moderator.id})",
                    delete_message_seconds=0,
                )

                log = make_log_embed(
                    "Member Banned",
                    discord.Color.red(),
                    moderator,
                    target,
                    reason,
                )

                await send_log(guild, log)
                message = f"⛔ **{target.display_name}** has been banned."

            elif self.action == "Softban":
                # Softban deletes the past 24 hours of messages, then unbans.
                await target.ban(
                    reason=f"Softban: {reason} | Moderator: {moderator.id}",
                    delete_message_seconds=86400,
                )

                try:
                    await guild.unban(
                        target,
                        reason=f"Softban completed by {moderator} ({moderator.id})",
                    )
                except discord.HTTPException:
                    # Do not claim the user was unbanned if this step failed.
                    log = make_log_embed(
                        "Softban Partially Completed",
                        discord.Color.red(),
                        moderator,
                        target,
                        reason,
                        extra="Ban succeeded, but unban failed. Manual review required.",
                    )
                    await send_log(guild, log)

                    return await interaction.followup.send(
                        f"⚠️ {target.mention} was banned, but the unban failed. "
                        "Please review the audit log and unban them manually if appropriate.",
                        ephemeral=True,
                    )

                log = make_log_embed(
                    "Member Softbanned",
                    discord.Color.orange(),
                    moderator,
                    target,
                    reason,
                    extra="Deleted messages from the previous 24 hours.",
                )

                await send_log(guild, log)

                message = (
                    f"🔨 **{target.display_name}** has been softbanned. "
                    "They are no longer banned."
                )

            else:
                return await interaction.followup.send(
                    "❌ Unknown moderation action.",
                    ephemeral=True,
                )

            await interaction.followup.send(
                message,
                ephemeral=True,
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Discord denied this action. Check my permissions "
                "and the server role hierarchy.",
                ephemeral=True,
            )

        except discord.NotFound:
            await interaction.followup.send(
                "❌ This member could not be found. They may have left the server.",
                ephemeral=True,
            )

        except discord.HTTPException as exc:
            await interaction.followup.send(
                f"❌ Discord could not complete the action (HTTP {exc.status}).",
                ephemeral=True,
            )


# =========================================================
# ACTION BUTTONS
# =========================================================

class ActionView(View):

    def __init__(self, target: discord.Member):
        super().__init__(timeout=PANEL_TIMEOUT)
        self.target = target

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if not isinstance(interaction.user, discord.Member):
            await respond_error(interaction, "❌ Server member required.")
            return False

        if not is_authorized(interaction.user):
            await respond_error(
                interaction,
                "❌ Only Staff and Executive Team can use this panel.",
            )
            return False

        error = can_moderate(
            interaction.user,
            self.target,
            interaction.guild,
        )

        if error:
            await respond_error(interaction, error)
            return False

        return True

    @discord.ui.button(
        label="Warn",
        emoji="⚠️",
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def warn(
        self,
        interaction: discord.Interaction,
        button: Button,
    ):
        await interaction.response.send_modal(
            ReasonModal("Warn", self.target)
        )

    @discord.ui.button(
        label="Timeout",
        emoji="⏱️",
        style=discord.ButtonStyle.primary,
        row=0,
    )
    async def timeout(
        self,
        interaction: discord.Interaction,
        button: Button,
    ):
        await interaction.response.send_modal(
            ReasonModal(
                "Timeout",
                self.target,
                "Duration (minutes)",
            )
        )

    @discord.ui.button(
        label="Remove Timeout",
        emoji="🔓",
        style=discord.ButtonStyle.success,
        row=0,
    )
    async def remove_timeout(
        self,
        interaction: discord.Interaction,
        button: Button,
    ):
        await interaction.response.send_modal(
            ReasonModal("Remove Timeout", self.target)
        )

    @discord.ui.button(
        label="Kick",
        emoji="👢",
        style=discord.ButtonStyle.danger,
        row=1,
    )
    async def kick(
        self,
        interaction: discord.Interaction,
        button: Button,
    ):
        await interaction.response.send_modal(
            ReasonModal("Kick", self.target)
        )

    @discord.ui.button(
        label="Softban",
        emoji="🔨",
        style=discord.ButtonStyle.danger,
        row=1,
    )
    async def softban(
        self,
        interaction: discord.Interaction,
        button: Button,
    ):
        await interaction.response.send_modal(
            ReasonModal("Softban", self.target)
        )

    @discord.ui.button(
        label="Ban",
        emoji="⛔",
        style=discord.ButtonStyle.danger,
        row=1,
    )
    async def ban(
        self,
        interaction: discord.Interaction,
        button: Button,
    ):
        await interaction.response.send_modal(
            ReasonModal("Ban", self.target)
        )


# =========================================================
# MEMBER SELECT
# =========================================================

class MemberSelect(Select):

    def __init__(self, members: list[discord.Member]):
        options = [
            discord.SelectOption(
                label=m.display_name[:100],
                description=f"@{m.name} • {m.top_role.name}"[:100],
                value=str(m.id),
                emoji="👤",
            )
            for m in members[:25]
        ]

        super().__init__(
            placeholder="Select a member to moderate...",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            return await respond_error(
                interaction,
                "❌ Server member required.",
            )

        if not is_authorized(interaction.user):
            return await respond_error(
                interaction,
                "❌ You are not authorized to use this panel.",
            )

        target_id = int(self.values[0])
        target = interaction.guild.get_member(target_id)

        if target is None:
            try:
                target = await interaction.guild.fetch_member(target_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return await respond_error(
                    interaction,
                    "⚠️ Member not found or no longer in the server.",
                )

        error = can_moderate(
            interaction.user,
            target,
            interaction.guild,
        )

        if error:
            return await respond_error(interaction, error)

        embed = discord.Embed(
            title=f"🛡️ Moderate — {target.display_name}",
            description="Choose an action below.",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )

        embed.set_thumbnail(url=target.display_avatar.url)

        embed.add_field(
            name="👤 Member",
            value=f"{target.mention}\n`{target.name}`",
            inline=True,
        )

        embed.add_field(
            name="🆔 User ID",
            value=f"`{target.id}`",
            inline=True,
        )

        embed.add_field(
            name="🏅 Highest Role",
            value=target.top_role.mention,
            inline=True,
        )

        embed.add_field(
            name="📅 Joined Server",
            value=(
                f"<t:{int(target.joined_at.timestamp())}:R>"
                if target.joined_at
                else "Unknown"
            ),
            inline=True,
        )

        timed_out = (
            target.timed_out_until is not None
            and target.timed_out_until > discord.utils.utcnow()
        )

        embed.add_field(
            name="⏱️ Timeout Status",
            value=(
                f"Until <t:{int(target.timed_out_until.timestamp())}:R>"
                if timed_out
                else "Not timed out"
            ),
            inline=True,
        )

        embed.add_field(
            name="🤖 Bot Account",
            value="Yes" if target.bot else "No",
            inline=True,
        )

        embed.set_footer(
            text="Akasa Air Virtual • Moderation Panel"
        )

        await interaction.response.send_message(
            embed=embed,
            view=ActionView(target),
            ephemeral=True,
        )


class MemberSelectView(View):

    def __init__(self, members: list[discord.Member]):
        super().__init__(timeout=PANEL_TIMEOUT)
        self.add_item(MemberSelect(members))


# =========================================================
# MODERATION COG
# =========================================================

class ModerationPanel(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="modpanel",
        description="Open the staff moderation panel",
    )
    @app_commands.guild_only()
    async def modpanel(
        self,
        interaction: discord.Interaction,
    ):
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message(
                "❌ This command must be used in a server.",
                ephemeral=True,
            )

        if not is_authorized(interaction.user):
            return await interaction.response.send_message(
                "❌ Only Staff and Executive Team can use this command.",
                ephemeral=True,
            )

        if interaction.guild is None:
            return await interaction.response.send_message(
                "❌ Server information is unavailable.",
                ephemeral=True,
            )

        # Use the member cache populated by the bot.
        # The first 25 eligible members are displayed alphabetically.
        members = sorted(
            [
                member
                for member in interaction.guild.members
                if not member.bot
                and member.id != interaction.user.id
            ],
            key=lambda member: member.display_name.casefold(),
        )

        if not members:
            return await interaction.response.send_message(
                "⚠️ No eligible members were found.",
                ephemeral=True,
            )

        displayed_members = members[:25]

        view = MemberSelectView(displayed_members)

        description = (
            f"Select a member below to open their moderation panel.\n"
            f"Showing **{len(displayed_members)}** of **{len(members)}** "
            "eligible members."
        )

        embed = discord.Embed(
            title="🛡️ Akasa Air Virtual — Moderation",
            description=description,
            color=discord.Color.orange(),
        )

        embed.set_footer(
            text="Staff and Executive Team only"
        )

        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationPanel(bot))
