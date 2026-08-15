import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
from datetime import datetime, timezone

STAFF_ROLE_ID = 1389824693388837035
EXEC_ROLE_ID = 1389824452778262589

LIVE_ROLE_ID = 1538100592579186688
LIVE_CHANNEL_ID = 1538102335837048862


def is_authorized(member: discord.Member) -> bool:
    return any(role.id in (STAFF_ROLE_ID, EXEC_ROLE_ID) for role in member.roles)


# ================= MODALS =================

class AddMemberModal(Modal):
    def __init__(self):
        super().__init__(title="Add Pilot to Live Fleet")

        self.member_id = TextInput(
            label="Discord User ID or @mention",
            placeholder="e.g. 123456789012345678",
            max_length=30
        )
        self.add_item(self.member_id)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.member_id.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        try:
            uid = int(raw)
        except ValueError:
            return await interaction.response.send_message(
                "❌ Invalid User ID. Paste the numeric ID or @mention.", ephemeral=True
            )

        member = interaction.guild.get_member(uid)
        if not member:
            return await interaction.response.send_message(
                f"❌ Member `{uid}` not found in this server.", ephemeral=True
            )

        live_role = interaction.guild.get_role(LIVE_ROLE_ID)
        if not live_role:
            return await interaction.response.send_message(
                "❌ Live Fleet role not found. Check the role ID.", ephemeral=True
            )

        if live_role in member.roles:
            return await interaction.response.send_message(
                f"⚠️ {member.mention} is already in Live Fleet mode.", ephemeral=True
            )

        try:
            await member.add_roles(live_role, reason=f"Added to Live Fleet by {interaction.user}")
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I do not have permission to assign this role.", ephemeral=True
            )

        # Send welcome message to live channel
        live_channel = interaction.guild.get_channel(LIVE_CHANNEL_ID)
        if live_channel:
            try:
                embed = discord.Embed(
                    title="✈️ Pilot Joined QPVA Live Fleet",
                    description=f"**{member.mention}** joined **QPVA Live Fleet**!",
                    color=discord.Color.green()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="👤 Pilot", value=member.mention, inline=True)
                embed.add_field(name="📅 Joined", value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>", inline=True)
                embed.set_footer(text="AkasaAirVirtual • QPVA Live Fleet")
                await live_channel.send(content=f"✈️ {member.mention} Joined QPVA Live Fleet!", embed=embed)
            except discord.Forbidden:
                pass

        await interaction.response.send_message(
            f"✅ **{member.display_name}** has been added to Live Fleet and notified.",
            ephemeral=True
        )


class RemoveMemberModal(Modal):
    def __init__(self):
        super().__init__(title="Remove Pilot from Live Fleet")

        self.member_id = TextInput(
            label="Discord User ID or @mention",
            placeholder="e.g. 123456789012345678",
            max_length=30
        )
        self.add_item(self.member_id)

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.member_id.value.strip().replace("<@", "").replace(">", "").replace("!", "")
        try:
            uid = int(raw)
        except ValueError:
            return await interaction.response.send_message(
                "❌ Invalid User ID.", ephemeral=True
            )

        member = interaction.guild.get_member(uid)
        if not member:
            return await interaction.response.send_message(
                f"❌ Member `{uid}` not found in this server.", ephemeral=True
            )

        live_role = interaction.guild.get_role(LIVE_ROLE_ID)
        if not live_role:
            return await interaction.response.send_message(
                "❌ Live Fleet role not found.", ephemeral=True
            )

        if live_role not in member.roles:
            return await interaction.response.send_message(
                f"⚠️ {member.mention} is not currently in Live Fleet mode.", ephemeral=True
            )

        try:
            await member.remove_roles(live_role, reason=f"Removed from Live Fleet by {interaction.user}")
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I do not have permission to remove this role.", ephemeral=True
            )

        # Send removal message to live channel
        live_channel = interaction.guild.get_channel(LIVE_CHANNEL_ID)
        if live_channel:
            try:
                embed = discord.Embed(
                    title="🛬 Pilot Left QPVA Live Fleet",
                    description=f"**{member.mention}** has left **QPVA Live Fleet**.",
                    color=discord.Color.red()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="👤 Pilot", value=member.mention, inline=True)
                embed.add_field(name="📅 Removed", value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>", inline=True)
                embed.set_footer(text="AkasaAirVirtual • QPVA Live Fleet")
                await live_channel.send(embed=embed)
            except discord.Forbidden:
                pass

        await interaction.response.send_message(
            f"✅ **{member.display_name}** has been removed from Live Fleet.",
            ephemeral=True
        )


# ================= VIEW ALL MODAL =================

class LiveFleetView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def auth_check(self, interaction: discord.Interaction) -> bool:
        if not is_authorized(interaction.user):
            await interaction.response.send_message(
                "❌ Only Staff and Executive Team can use this panel.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Add Member", emoji="➕", style=discord.ButtonStyle.success, custom_id="live_add")
    async def add_member(self, interaction: discord.Interaction, button: Button):
        if not await self.auth_check(interaction):
            return
        await interaction.response.send_modal(AddMemberModal())

    @discord.ui.button(label="Remove Member", emoji="➖", style=discord.ButtonStyle.danger, custom_id="live_remove")
    async def remove_member(self, interaction: discord.Interaction, button: Button):
        if not await self.auth_check(interaction):
            return
        await interaction.response.send_modal(RemoveMemberModal())

    @discord.ui.button(label="View Live Fleet", emoji="👥", style=discord.ButtonStyle.primary, custom_id="live_view")
    async def view_fleet(self, interaction: discord.Interaction, button: Button):
        if not await self.auth_check(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        live_role = interaction.guild.get_role(LIVE_ROLE_ID)
        if not live_role:
            return await interaction.followup.send("❌ Live Fleet role not found.", ephemeral=True)

        members = live_role.members
        if not members:
            return await interaction.followup.send(
                "⚠️ No pilots are currently in Live Fleet mode.", ephemeral=True
            )

        embed = discord.Embed(
            title=f"✈️ QPVA Live Fleet — {len(members)} Active",
            color=discord.Color.green()
        )

        lines = [f"`#{i+1}` {m.mention} — {m.display_name}" for i, m in enumerate(members)]
        embed.description = "\n".join(lines[:30])
        if len(members) > 30:
            embed.description += f"\n*...and {len(members) - 30} more*"

        embed.set_footer(text="AkasaAirVirtual • QPVA Live Fleet")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Remove All", emoji="🗑️", style=discord.ButtonStyle.danger, custom_id="live_remove_all", row=1)
    async def remove_all(self, interaction: discord.Interaction, button: Button):
        if not await self.auth_check(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        live_role = interaction.guild.get_role(LIVE_ROLE_ID)
        if not live_role:
            return await interaction.followup.send("❌ Live Fleet role not found.", ephemeral=True)

        members = live_role.members
        if not members:
            return await interaction.followup.send(
                "⚠️ No pilots are currently in Live Fleet mode.", ephemeral=True
            )

        removed = 0
        for member in members:
            try:
                await member.remove_roles(live_role, reason=f"Live Fleet cleared by {interaction.user}")
                removed += 1
            except Exception:
                pass

        live_channel = interaction.guild.get_channel(LIVE_CHANNEL_ID)
        if live_channel:
            try:
                await live_channel.send(
                    f"🛬 **QPVA Live Fleet session ended.** All **{removed}** pilots have been removed from Live Fleet mode."
                )
            except discord.Forbidden:
                pass

        await interaction.followup.send(
            f"✅ Removed **{removed}** pilot(s) from Live Fleet mode.", ephemeral=True
        )


# ================= COG =================

class LiveControlPanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="live_control_panel", description="Send the Live Fleet control panel (staff/exec only)")
    @app_commands.describe(
        channel="Channel to post the panel in",
        image="Optional banner image URL"
    )
    async def live_control_panel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        image: str = None
    ):
        if not is_authorized(interaction.user):
            return await interaction.response.send_message(
                "❌ Only Staff and Executive Team can send this panel.", ephemeral=True
            )

        embed = discord.Embed(
            title="✈️ QPVA Live Fleet — Control Panel",
            description=(
                "Manage pilots in **QPVA Live Fleet** mode.\n\n"
                "➕ **Add Member** — Grant a pilot Live Fleet access and role\n"
                "➖ **Remove Member** — Remove a pilot from Live Fleet\n"
                "👥 **View Live Fleet** — See all currently active pilots\n"
                "🗑️ **Remove All** — End the session and remove all pilots\n\n"
                "*Access restricted to Staff and Executive Team.*"
            ),
            color=discord.Color.orange()
        )

        if image:
            embed.set_image(url=image)

        embed.set_footer(text="AkasaAirVirtual • QPVA Live Fleet Control Panel")

        view = LiveFleetView()
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            f"✅ Live Control Panel sent in {channel.mention}", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(LiveControlPanel(bot))
    bot.add_view(LiveFleetView())
