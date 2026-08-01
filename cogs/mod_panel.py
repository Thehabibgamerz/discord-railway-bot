import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput, Select
from datetime import timedelta, datetime, timezone

STAFF_ROLE_ID = 1389824693388837035
EXEC_ROLE_ID = 1389824452778262589
LOG_CHANNEL_ID = 1506970182680182805

MAX_TIMEOUT_MINUTES = 40320  # 28 days


def is_authorized(member: discord.Member) -> bool:
    return any(role.id in (STAFF_ROLE_ID, EXEC_ROLE_ID) for role in member.roles)


def can_moderate(moderator: discord.Member, target: discord.Member, guild: discord.Guild) -> str | None:
    if target.id == moderator.id:
        return "❌ You cannot target yourself."
    if target.id == guild.me.id:
        return "❌ You cannot target me."
    if moderator.id != guild.owner_id:
        if target.top_role >= moderator.top_role:
            return "❌ You cannot moderate this user (equal or higher role)."
    if target.top_role >= guild.me.top_role:
        return "❌ I cannot moderate this user — their role is too high."
    return None


async def send_log(guild: discord.Guild, embed: discord.Embed):
    channel = guild.get_channel(LOG_CHANNEL_ID)
    if channel:
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass


def make_log_embed(action: str, color: discord.Color, moderator: discord.Member,
                   target: discord.Member, reason: str, extra: str = None) -> discord.Embed:
    embed = discord.Embed(title=f"🛡️ {action}", color=color,
                          timestamp=datetime.now(timezone.utc))
    embed.add_field(name="👤 Member", value=target.mention, inline=True)
    embed.add_field(name="🎭 Moderator", value=moderator.mention, inline=True)
    embed.add_field(name="📋 Reason", value=reason, inline=False)
    if extra:
        embed.add_field(name="ℹ️ Details", value=extra, inline=False)
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.set_footer(text=f"User ID: {target.id}")
    return embed


# ================= ACTION MODALS =================

class ReasonModal(Modal):
    def __init__(self, action: str, target: discord.Member, extra_field: str = None):
        super().__init__(title=f"{action} — {target.display_name}")
        self.action = action
        self.target = target

        self.reason = TextInput(
            label="Reason",
            placeholder="Enter reason...",
            max_length=500
        )
        self.add_item(self.reason)

        self.extra_input = None
        if extra_field:
            self.extra_input = TextInput(
                label=extra_field,
                placeholder="e.g. 60 for 60 minutes" if "minute" in extra_field.lower() else "",
                max_length=10
            )
            self.add_item(self.extra_input)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason.value.strip()
        target = self.target
        guild = interaction.guild

        error = can_moderate(interaction.user, target, guild)
        if error:
            return await interaction.response.send_message(error, ephemeral=True)

        try:
            if self.action == "Kick":
                await target.kick(reason=reason)
                color = discord.Color.orange()
                log = make_log_embed("Member Kicked", color, interaction.user, target, reason)
                await interaction.response.send_message(
                    f"✅ **{target.display_name}** has been kicked.", ephemeral=True
                )

            elif self.action == "Ban":
                await target.ban(reason=reason)
                color = discord.Color.red()
                log = make_log_embed("Member Banned", color, interaction.user, target, reason)
                await interaction.response.send_message(
                    f"✅ **{target.display_name}** has been banned.", ephemeral=True
                )

            elif self.action == "Warn":
                log = make_log_embed("Member Warned", discord.Color.gold(), interaction.user, target, reason)
                await interaction.response.send_message(
                    f"⚠️ **{target.display_name}** has been warned.", ephemeral=True
                )
                try:
                    await target.send(
                        f"⚠️ You were warned in **{guild.name}**\nReason: {reason}"
                    )
                except discord.Forbidden:
                    pass

            elif self.action == "Timeout":
                minutes_str = self.extra_input.value.strip() if self.extra_input else "60"
                try:
                    minutes = int(minutes_str)
                except ValueError:
                    return await interaction.response.send_message(
                        "❌ Invalid minutes value.", ephemeral=True
                    )
                if minutes <= 0 or minutes > MAX_TIMEOUT_MINUTES:
                    return await interaction.response.send_message(
                        f"❌ Minutes must be between 1 and {MAX_TIMEOUT_MINUTES}.", ephemeral=True
                    )
                await target.timeout(timedelta(minutes=minutes), reason=reason)
                log = make_log_embed(
                    "Member Timed Out", discord.Color.yellow(),
                    interaction.user, target, reason,
                    extra=f"{minutes} minutes"
                )
                await interaction.response.send_message(
                    f"⏱️ **{target.display_name}** has been timed out for **{minutes}** minutes.",
                    ephemeral=True
                )

            elif self.action == "Remove Timeout":
                await target.timeout(None, reason=reason)
                log = make_log_embed("Timeout Removed", discord.Color.green(), interaction.user, target, reason)
                await interaction.response.send_message(
                    f"✅ Timeout removed from **{target.display_name}**.", ephemeral=True
                )

            elif self.action == "Softban":
                # Ban then immediately unban — deletes recent messages
                await target.ban(reason=f"Softban: {reason}", delete_message_days=1)
                await guild.unban(target, reason="Softban — immediate unban")
                log = make_log_embed("Member Softbanned", discord.Color.orange(), interaction.user, target, reason)
                await interaction.response.send_message(
                    f"✅ **{target.display_name}** has been softbanned (messages deleted, not banned).",
                    ephemeral=True
                )

            else:
                return

            await send_log(guild, log)

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to perform this action.", ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ Failed: {e}", ephemeral=True)


# ================= ACTION BUTTONS VIEW =================

class ActionView(View):
    def __init__(self, target: discord.Member):
        super().__init__(timeout=120)
        self.target = target

    async def auth_check(self, interaction: discord.Interaction) -> bool:
        if not is_authorized(interaction.user):
            await interaction.response.send_message(
                "❌ Only Staff can use this panel.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Warn", emoji="⚠️", style=discord.ButtonStyle.secondary, row=0)
    async def warn(self, interaction: discord.Interaction, button: Button):
        if not await self.auth_check(interaction):
            return
        await interaction.response.send_modal(ReasonModal("Warn", self.target))

    @discord.ui.button(label="Timeout", emoji="⏱️", style=discord.ButtonStyle.primary, row=0)
    async def timeout(self, interaction: discord.Interaction, button: Button):
        if not await self.auth_check(interaction):
            return
        await interaction.response.send_modal(ReasonModal("Timeout", self.target, "Duration (minutes)"))

    @discord.ui.button(label="Remove Timeout", emoji="🔓", style=discord.ButtonStyle.success, row=0)
    async def remove_timeout(self, interaction: discord.Interaction, button: Button):
        if not await self.auth_check(interaction):
            return
        await interaction.response.send_modal(ReasonModal("Remove Timeout", self.target))

    @discord.ui.button(label="Kick", emoji="👢", style=discord.ButtonStyle.danger, row=1)
    async def kick(self, interaction: discord.Interaction, button: Button):
        if not await self.auth_check(interaction):
            return
        await interaction.response.send_modal(ReasonModal("Kick", self.target))

    @discord.ui.button(label="Softban", emoji="🔨", style=discord.ButtonStyle.danger, row=1)
    async def softban(self, interaction: discord.Interaction, button: Button):
        if not await self.auth_check(interaction):
            return
        await interaction.response.send_modal(ReasonModal("Softban", self.target))

    @discord.ui.button(label="Ban", emoji="⛔", style=discord.ButtonStyle.danger, row=1)
    async def ban(self, interaction: discord.Interaction, button: Button):
        if not await self.auth_check(interaction):
            return
        await interaction.response.send_modal(ReasonModal("Ban", self.target))


# ================= MEMBER SELECT VIEW =================

class MemberSelectView(View):
    def __init__(self, members: list[discord.Member]):
        super().__init__(timeout=60)

        options = [
            discord.SelectOption(
                label=m.display_name[:100],
                description=f"@{m.name} · {m.top_role.name}",
                value=str(m.id),
                emoji="👤"
            )
            for m in members[:25]
        ]

        select = Select(
            placeholder="Select a member to moderate...",
            options=options,
            min_values=1,
            max_values=1
        )
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        target_id = int(self.children[0].values[0])
        target = interaction.guild.get_member(target_id)

        if not target:
            return await interaction.response.send_message(
                "⚠️ Member not found.", ephemeral=True
            )

        embed = discord.Embed(
            title=f"🛡️ Moderate — {target.display_name}",
            color=discord.Color.orange()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="👤 User", value=target.mention, inline=True)
        embed.add_field(name="🆔 ID", value=str(target.id), inline=True)
        embed.add_field(name="🏅 Top Role", value=target.top_role.mention, inline=True)
        embed.add_field(
            name="📅 Joined",
            value=f"<t:{int(target.joined_at.timestamp())}:R>" if target.joined_at else "N/A",
            inline=True
        )
        embed.add_field(
            name="⏱️ Timed Out",
            value="Yes" if target.timed_out_until and target.timed_out_until > discord.utils.utcnow() else "No",
            inline=True
        )
        embed.set_footer(text="Select an action below — AkasaAirVirtual Moderation")

        await interaction.response.send_message(
            embed=embed,
            view=ActionView(target),
            ephemeral=True
        )


# ================= COG =================

class ModerationPanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="modpanel", description="Open the moderation action panel (staff only)")
    async def modpanel(self, interaction: discord.Interaction):
        if not is_authorized(interaction.user):
            return await interaction.response.send_message(
                "❌ Only Staff and Executive Team can use this command.", ephemeral=True
            )

        # Get non-bot members excluding the moderator, sorted by display name
        members = sorted(
            [m for m in interaction.guild.members if not m.bot and m.id != interaction.user.id],
            key=lambda m: m.display_name.lower()
        )

        if not members:
            return await interaction.response.send_message(
                "⚠️ No members found.", ephemeral=True
            )

        await interaction.response.send_message(
            "👤 Select a member to moderate:",
            view=MemberSelectView(members),
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(ModerationPanel(bot))
