
# ================================================================
# ✈️ AKASA AIR VIRTUAL — ADVANCED TICKET SYSTEM
# File: cogs/tickets.py
# Python 3.10+ | discord.py 2.x
# ================================================================

import asyncio
import logging
import re
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

# ================= CONFIGURATION =================

TICKET_CATEGORY_ID = 1389838715647692900
LOG_CHANNEL_ID = 1389842003906265098

STAFF_ROLE_ID = 1389824693388837035
GENERAL_ROLE_ID = 1389824693388837035
RECRUIT_ROLE_ID = 1432616013257773227
EXEC_ROLE_ID = 1389824452778262589
PIREP_ROLE_ID = 1432615867488669706
ROUTE_ROLE_ID = 1432615814921453649

# Optional: closed ticket category. Leave as None to keep tickets
# in their existing category.
CLOSED_CATEGORY_ID = None

# Optional: set True to stop users opening a second ticket
# while they already have an open ticket.
PREVENT_DUPLICATE_TICKETS = True

# Set to False if you do not want ticket creation to ping the
# relevant support role.
PING_SUPPORT_ROLE = True

ORANGE = discord.Color.from_rgb(255, 125, 35)
GREEN = discord.Color.green()
RED = discord.Color.red()
BLUE = discord.Color.blurple()

CATEGORY_CONFIG = {
    "General Support": {
        "prefix": "support",
        "role_id": GENERAL_ROLE_ID,
        "emoji": "🎫",
        "description": "General help and questions",
    },
    "Recruitments": {
        "prefix": "recruitment",
        "role_id": RECRUIT_ROLE_ID,
        "emoji": "🧑‍✈️",
        "description": "Pilot applications and recruitment",
    },
    "Executive Team Support": {
        "prefix": "exec",
        "role_id": EXEC_ROLE_ID,
        "emoji": "⭐",
        "description": "Management and executive support",
    },
    "PIREP Support": {
        "prefix": "pirep",
        "role_id": PIREP_ROLE_ID,
        "emoji": "📋",
        "description": "Flight report assistance",
    },
    "Route Support": {
        "prefix": "route",
        "role_id": ROUTE_ROLE_ID,
        "emoji": "🗺️",
        "description": "Routes and scheduling support",
    },
}


# ================= HELPERS =================

def is_staff(member: discord.abc.User) -> bool:
    """Check whether the user has an authorized support role."""
    if not isinstance(member, discord.Member):
        return False

    authorized_roles = {
        STAFF_ROLE_ID,
        EXEC_ROLE_ID,
    }

    return (
        member.guild_permissions.administrator
        or any(role.id in authorized_roles for role in member.roles)
    )


def get_ticket_owner_id(channel: discord.abc.GuildChannel) -> int | None:
    """Read ticket owner ID from the channel topic."""
    topic = getattr(channel, "topic", None)

    if not topic:
        return None

    match = re.search(r"Ticket Owner:\s*(\d+)", topic)

    if match:
        return int(match.group(1))

    return None


def get_ticket_claimed_id(channel: discord.abc.GuildChannel) -> int | None:
    topic = getattr(channel, "topic", None)

    if not topic:
        return None

    match = re.search(r"Claimed By:\s*(\d+)", topic)

    if match:
        return int(match.group(1))

    return None


def get_ticket_category_name(channel: discord.TextChannel) -> str:
    topic = channel.topic or ""
    match = re.search(r"Ticket Category:\s*([^|]+)", topic)

    if match:
        return match.group(1).strip()

    return "Unknown"


def safe_username(user: discord.abc.User) -> str:
    """Create a channel-name-friendly username."""
    username = user.name.lower()
    username = re.sub(r"[^a-z0-9-]", "-", username)
    username = re.sub(r"-+", "-", username).strip("-")
    return username[:40] or "user"


def make_ticket_embed(
    title: str,
    description: str,
    color: discord.Color = ORANGE,
) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=discord.utils.utcnow(),
    )


async def send_log(
    guild: discord.Guild,
    embed: discord.Embed,
) -> None:
    """Send a log without making the main ticket action fail."""
    channel = guild.get_channel(LOG_CHANNEL_ID)

    if channel is None:
        try:
            channel = await guild.fetch_channel(LOG_CHANNEL_ID)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            logger.warning("Ticket log channel %s unavailable.", LOG_CHANNEL_ID)
            return

    if not isinstance(channel, discord.TextChannel):
        logger.warning("Ticket log channel ID is not a text channel.")
        return

    try:
        await channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        logger.exception("Failed to send ticket log.")


async def private_error(
    interaction: discord.Interaction,
    message: str,
) -> None:
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.HTTPException:
        logger.exception("Failed to respond to ticket interaction.")


async def find_ticket_category(
    guild: discord.Guild,
) -> discord.CategoryChannel | None:
    channel = guild.get_channel(TICKET_CATEGORY_ID)

    if isinstance(channel, discord.CategoryChannel):
        return channel

    try:
        channel = await guild.fetch_channel(TICKET_CATEGORY_ID)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None

    return channel if isinstance(channel, discord.CategoryChannel) else None


def ticket_log_embed(
    title: str,
    user: discord.abc.User,
    channel: discord.TextChannel,
    description: str,
    color: discord.Color,
) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="User / Staff", value=f"{user.mention}\n`{user.id}`")
    embed.add_field(name="Ticket", value=f"{channel.mention}\n`{channel.name}`")
    embed.add_field(
        name="Ticket ID",
        value=f"`{channel.id}`",
        inline=False,
    )
    return embed


# ================= TICKET DROPDOWN =================

class TicketDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=name,
                description=config["description"],
                emoji=config["emoji"],
            )
            for name, config in CATEGORY_CONFIG.items()
        ]

        super().__init__(
            placeholder="✈️ Select a support category",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_dropdown",
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild

        if guild is None:
            return await private_error(
                interaction,
                "This panel can only be used inside a server.",
            )

        category_name = self.values[0]
        config = CATEGORY_CONFIG.get(category_name)

        if config is None:
            return await private_error(
                interaction,
                "Invalid ticket category. Please try again.",
            )

        # Acknowledge before making Discord API requests.
        await interaction.response.defer(ephemeral=True, thinking=True)

        category = await find_ticket_category(guild)

        if category is None:
            return await interaction.followup.send(
                "❌ The configured ticket category was not found. "
                "Please notify an administrator.",
                ephemeral=True,
            )

        # Prevent duplicate tickets for this user.
        if PREVENT_DUPLICATE_TICKETS:
            for channel in category.text_channels:
                if (
                    get_ticket_owner_id(channel) == interaction.user.id
                    and not channel.name.startswith("closed-")
                ):
                    await interaction.followup.send(
                        f"⚠️ You already have a ticket open: {channel.mention}",
                        ephemeral=True,
                    )
                    return

        prefix = config["prefix"]
        username = safe_username(interaction.user)

        # Determine the next number using existing channels.
        highest_number = 0

        for channel in category.text_channels:
            match = re.search(
                rf"(?:^|-)({re.escape(prefix)}|"
                rf"(?!) )",
                channel.name,
            )
            # Ticket numbering is read from the end of the channel name.
            number_match = re.search(r"-(\d{3,})$", channel.name)
            if number_match:
                try:
                    highest_number = max(
                        highest_number,
                        int(number_match.group(1)),
                    )
                except ValueError:
                    pass

        next_number = highest_number + 1
        channel_name = f"{prefix}-{username}-{next_number:03d}"[:100]

        support_role = guild.get_role(config["role_id"])
        staff_role = guild.get_role(STAFF_ROLE_ID)
        exec_role = guild.get_role(EXEC_ROLE_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False,
            ),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                attach_files=True,
                embed_links=True,
                read_message_history=True,
                add_reactions=True,
            ),
        }

        # General support staff can access all tickets.
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
                attach_files=True,
                embed_links=True,
            )

        # Executive support role can access executive tickets.
        if category_name == "Executive Team Support" and exec_role:
            overwrites[exec_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
                attach_files=True,
                embed_links=True,
            )

        # Give the category-specific support role access to its tickets.
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            )

        try:
            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=(
                    f"Ticket Owner: {interaction.user.id} | "
                    f"Ticket Category: {category_name} | "
                    "Claimed By: none"
                ),
                reason=f"Ticket opened by {interaction.user}",
            )
        except discord.Forbidden:
            return await interaction.followup.send(
                "❌ I cannot create tickets. Check my Manage Channels "
                "and channel permission settings.",
                ephemeral=True,
            )
        except discord.HTTPException:
            logger.exception("Failed to create ticket.")
            return await interaction.followup.send(
                "❌ Failed to create the ticket. Please try again.",
                ephemeral=True,
            )

        embed = discord.Embed(
            title="🎫 Support Ticket Opened",
            description=(
                f"Welcome {interaction.user.mention}!\n\n"
                f"**Category:** {category_name}\n\n"
                "Please explain your issue clearly and include any "
                "necessary details.\n\n"
                "• A staff member will assist you shortly.\n"
                "• Avoid repeatedly pinging staff.\n"
                "• Please remain respectful.\n\n"
                "Thank you for choosing **Akasa Air Virtual** ✈️"
            ),
            color=ORANGE,
            timestamp=discord.utils.utcnow(),
        )

        embed.add_field(
            name="📂 Ticket Information",
            value=(
                f"**Opened By:** {interaction.user.mention}\n"
                f"**Category:** {category_name}\n"
                f"**Created:** <t:{int(discord.utils.utcnow().timestamp())}:F>"
            ),
            inline=False,
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(
            text=f"Ticket ID: {channel.id} • Akasa Air Virtual",
            icon_url=guild.icon.url if guild.icon else None,
        )

        role_mention = (
            f"<@&{config['role_id']}>"
            if PING_SUPPORT_ROLE and support_role
            else ""
        )

        try:
            await channel.send(
                content=role_mention or None,
                embed=embed,
                view=TicketControls(),
                allowed_mentions=discord.AllowedMentions(
                    roles=True,
                    users=True,
                    everyone=False,
                ),
            )
        except discord.HTTPException:
            logger.exception("Ticket created but welcome message failed.")

        await send_log(
            guild,
            ticket_log_embed(
                "📩 Ticket Created",
                interaction.user,
                channel,
                f"**Category:** {category_name}",
                GREEN,
            ),
        )

        await interaction.followup.send(
            f"✅ Your ticket has been created: {channel.mention}",
            ephemeral=True,
        )


# ================= PANEL VIEW =================

class TicketPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())


# ================= CLAIM / CLOSE CONTROLS =================

class TicketControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Claim",
        emoji="👨‍✈️",
        style=discord.ButtonStyle.success,
        custom_id="ticket_claim",
    )
    async def claim(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if not is_staff(interaction.user):
            return await private_error(
                interaction,
                "❌ Only authorized staff members can claim tickets.",
            )

        channel = interaction.channel
        guild = interaction.guild

        if not isinstance(channel, discord.TextChannel) or guild is None:
            return await private_error(interaction, "Invalid ticket channel.")

        claimed_id = get_ticket_claimed_id(channel)

        if claimed_id:
            claimed_member = guild.get_member(claimed_id)
            claimed_name = (
                claimed_member.mention if claimed_member else f"`{claimed_id}`"
            )
            return await private_error(
                interaction,
                f"⚠️ This ticket has already been claimed by {claimed_name}.",
            )

        # Preserve the original category and ticket number.
        base_name = channel.name
        if base_name.startswith("claimed-"):
            base_name = base_name[len("claimed-"):]

        new_name = f"claimed-{base_name}"[:100]
        old_topic = channel.topic or ""
        topic = re.sub(
            r"Claimed By:\s*(none|\d+)",
            f"Claimed By: {interaction.user.id}",
            old_topic,
            flags=re.IGNORECASE,
        )

        # Acknowledge immediately; channel editing can take time.
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            await channel.edit(
                name=new_name,
                topic=topic,
                reason=f"Ticket claimed by {interaction.user} ({interaction.user.id})",
            )

            # Disable Claim on the original ticket control message.
            button.disabled = True
            try:
                await interaction.message.edit(view=self)
            except discord.HTTPException:
                logger.warning("Could not update claim button.")

            embed = make_ticket_embed(
                "✅ Ticket Claimed",
                (
                    f"👨‍✈️ **Claimed By:** {interaction.user.mention}\n"
                    f"📂 **Ticket:** {channel.mention}\n\n"
                    "This staff member is now responsible for handling "
                    "the ticket."
                ),
                GREEN,
            )
            await channel.send(embed=embed)

            await send_log(
                guild,
                ticket_log_embed(
                    "👨‍✈️ Ticket Claimed",
                    interaction.user,
                    channel,
                    f"**New Name:** `{new_name}`",
                    GREEN,
                ),
            )

            await interaction.followup.send(
                f"✅ You claimed the ticket. Channel renamed to `{new_name}`.",
                ephemeral=True,
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I need Manage Channels permission to rename the ticket.",
                ephemeral=True,
            )
        except discord.HTTPException:
            logger.exception("Ticket claim failed.")
            await interaction.followup.send(
                "❌ Could not claim the ticket. Please try again.",
                ephemeral=True,
            )

    @discord.ui.button(
        label="Close",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_close",
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if not is_staff(interaction.user):
            return await private_error(
                interaction,
                "❌ Only authorized staff members can close tickets.",
            )

        await interaction.response.send_message(
            embed=make_ticket_embed(
                "⚠️ Confirm Ticket Closure",
                "Are you sure you want to close this ticket?",
            ),
            view=TicketCloseConfirm(),
            ephemeral=True,
        )


# ================= CLOSE CONFIRMATION =================

class TicketCloseConfirm(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(
        label="Confirm Close",
        emoji="✅",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_close_confirm",
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if not is_staff(interaction.user):
            return await private_error(interaction, "❌ Staff only.")

        channel = interaction.channel
        guild = interaction.guild

        if not isinstance(channel, discord.TextChannel) or guild is None:
            return await private_error(interaction, "Invalid ticket channel.")

        await interaction.response.defer(ephemeral=True, thinking=True)

        owner_id = get_ticket_owner_id(channel)
        owner = guild.get_member(owner_id) if owner_id else None

        try:
            # Hide the ticket from @everyone.
            await channel.set_permissions(
                guild.default_role,
                view_channel=False,
            )

            # Lock the owner.
            if owner:
                await channel.set_permissions(
                    owner,
                    view_channel=True,
                    send_messages=False,
                    add_reactions=False,
                    attach_files=False,
                    embed_links=False,
                    read_message_history=True,
                )

            # Lock other explicitly added members too.
            for target, overwrite in list(channel.overwrites.items()):
                if isinstance(target, discord.Member) and (
                    not owner or target.id != owner.id
                ):
                    if overwrite.view_channel:
                        overwrite.send_messages = False
                        overwrite.add_reactions = False
                        overwrite.attach_files = False
                        overwrite.embed_links = False
                        await channel.set_permissions(target, overwrite=overwrite)

            # Optionally move the channel to a closed category.
            if CLOSED_CATEGORY_ID:
                closed_category = guild.get_channel(CLOSED_CATEGORY_ID)
                if isinstance(closed_category, discord.CategoryChannel):
                    await channel.edit(category=closed_category)

            # Disable the confirmation buttons.
            for item in self.children:
                item.disabled = True

            try:
                await interaction.message.edit(view=self)
            except discord.HTTPException:
                pass

            await channel.send(
                embed=make_ticket_embed(
                    "🔒 Ticket Closed",
                    (
                        f"This ticket was closed by {interaction.user.mention}.\n\n"
                        "Only authorized staff can send messages now. "
                        "Staff can reopen or delete this ticket using the controls below."
                    ),
                    RED,
                ),
                view=TicketCloseControls(),
            )

            await send_log(
                guild,
                ticket_log_embed(
                    "🔒 Ticket Closed",
                    interaction.user,
                    channel,
                    "Ticket access was locked.",
                    RED,
                ),
            )

            await interaction.followup.send(
                f"🔒 {channel.mention} has been closed.",
                ephemeral=True,
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I cannot change ticket permissions. Check my Manage Channels permission.",
                ephemeral=True,
            )
        except discord.HTTPException:
            logger.exception("Failed to close ticket.")
            await interaction.followup.send(
                "❌ Ticket closure failed. Check my permissions and try again.",
                ephemeral=True,
            )

    @discord.ui.button(
        label="Cancel",
        emoji="❌",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_close_cancel",
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            embed=make_ticket_embed(
                "❎ Closure Cancelled",
                "The ticket remains open.",
                BLUE,
            ),
            view=self,
        )


# ================= REOPEN / DELETE CONTROLS =================

class TicketCloseControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Reopen",
        emoji="🔓",
        style=discord.ButtonStyle.success,
        custom_id="ticket_reopen",
    )
    async def reopen(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if not is_staff(interaction.user):
            return await private_error(interaction, "❌ Staff only.")

        channel = interaction.channel
        guild = interaction.guild

        if not isinstance(channel, discord.TextChannel) or guild is None:
            return await private_error(interaction, "Invalid ticket channel.")

        await interaction.response.defer(ephemeral=True, thinking=True)

        owner_id = get_ticket_owner_id(channel)
        owner = guild.get_member(owner_id) if owner_id else None

        try:
            # Move the ticket back to its normal category.
            category = await find_ticket_category(guild)
            if category:
                await channel.edit(category=category)

            # Restore the ticket owner's access.
            if owner:
                await channel.set_permissions(
                    owner,
                    view_channel=True,
                    send_messages=True,
                    add_reactions=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True,
                )

            # Restore access for other explicitly added members.
            for target, overwrite in list(channel.overwrites.items()):
                if isinstance(target, discord.Member) and (
                    not owner or target.id != owner.id
                ):
                    if overwrite.view_channel:
                        overwrite.send_messages = True
                        overwrite.add_reactions = True
                        overwrite.attach_files = True
                        overwrite.embed_links = True
                        await channel.set_permissions(target, overwrite=overwrite)

            await channel.set_permissions(
                guild.default_role,
                view_channel=False,
            )

            # Remove "closed-" if present, but preserve a claimed prefix.
            if channel.name.startswith("closed-"):
                await channel.edit(name=channel.name[len("closed-"):])

            # Disable old closed-ticket controls.
            for item in self.children:
                item.disabled = True

            try:
                await interaction.message.edit(view=self)
            except discord.HTTPException:
                pass

            await channel.send(
                embed=make_ticket_embed(
                    "🔓 Ticket Reopened",
                    f"This ticket was reopened by {interaction.user.mention}.",
                    GREEN,
                ),
                view=TicketControls(),
            )

            await send_log(
                guild,
                ticket_log_embed(
                    "🔓 Ticket Reopened",
                    interaction.user,
                    channel,
                    "Ticket access was restored.",
                    GREEN,
                ),
            )

            await interaction.followup.send(
                f"✅ {channel.mention} has been reopened.",
                ephemeral=True,
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I cannot restore ticket permissions. Check Manage Channels.",
                ephemeral=True,
            )
        except discord.HTTPException:
            logger.exception("Failed to reopen ticket.")
            await interaction.followup.send(
                "❌ Failed to reopen ticket.",
                ephemeral=True,
            )

    @discord.ui.button(
        label="Delete",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_delete",
    )
    async def delete(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if not is_staff(interaction.user):
            return await private_error(interaction, "❌ Staff only.")

        await interaction.response.send_message(
            "⚠️ Are you sure you want to permanently delete this ticket?",
            view=TicketDeleteConfirm(),
            ephemeral=True,
        )


class TicketDeleteConfirm(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)

    @discord.ui.button(
        label="Confirm Delete",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
    )
    async def confirm_delete(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if not is_staff(interaction.user):
            return await private_error(interaction, "❌ Staff only.")

        channel = interaction.channel
        guild = interaction.guild

        if not isinstance(channel, discord.TextChannel) or guild is None:
            return await private_error(interaction, "Invalid ticket channel.")

        # Log before deleting the channel.
        await send_log(
            guild,
            ticket_log_embed(
                "🗑️ Ticket Deleted",
                interaction.user,
                channel,
                "Ticket permanently deleted.",
                RED,
            ),
        )

        await interaction.response.send_message(
            "🗑️ Ticket will be deleted in 5 seconds.",
            ephemeral=True,
        )

        await asyncio.sleep(5)

        try:
            await channel.delete(
                reason=f"Ticket deleted by {interaction.user} ({interaction.user.id})"
            )
        except discord.Forbidden:
            logger.error("Missing permission to delete ticket %s", channel.id)
        except discord.HTTPException:
            logger.exception("Failed to delete ticket %s", channel.id)

    @discord.ui.button(
        label="Cancel",
        emoji="❌",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel_delete(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content="Deletion cancelled.",
            view=self,
        )


# ================= TICKET PANEL EMBED =================

def create_panel_embed(guild: discord.Guild) -> discord.Embed:
    embed = discord.Embed(
        title="🎫 Akasa Air Virtual Support Center",
        description=(
            "Welcome to the support center of **Akasa Air Virtual** ✈️\n\n"
            "Need assistance with recruitment, routes, PIREPs, management, "
            "or general questions? Select a category below.\n\n"
            "### 📂 Available Categories\n"
            "🎫 **General Support**\n"
            "General questions and technical assistance.\n\n"
            "🧑‍✈️ **Recruitments**\n"
            "Pilot applications and onboarding.\n\n"
            "⭐ **Executive Team Support**\n"
            "Management and confidential matters.\n\n"
            "📋 **PIREP Support**\n"
            "Flight report and logging assistance.\n\n"
            "🗺️ **Route Support**\n"
            "Route information and scheduling.\n\n"
            "### ⚠️ Before Opening a Ticket\n"
            "• Explain your issue clearly.\n"
            "• Be respectful to the support team.\n"
            "• Avoid opening duplicate tickets.\n\n"
            "Select a category below to get started."
        ),
        color=ORANGE,
    )

    embed.set_footer(
        text="Akasa Air Virtual • Support System",
        icon_url=guild.icon.url if guild.icon else None,
    )

    return embed


# ================= COG =================

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="ticketpanel",
        description="Send the Akasa Air Virtual ticket panel.",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        channel="Channel where the support panel will be sent",
        image="Optional image URL for the panel",
    )
    async def ticketpanel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        image: str | None = None,
    ):
        if not is_staff(interaction.user):
            return await private_error(
                interaction,
                "❌ Only authorized staff can send the ticket panel.",
            )

        embed = create_panel_embed(interaction.guild)

        if image:
            if not image.startswith(("https://", "http://")):
                return await private_error(
                    interaction,
                    "Please provide a valid image URL starting with http:// or https://.",
                )
            embed.set_image(url=image)

        try:
            await channel.send(
                embed=embed,
                view=TicketPanel(),
            )
        except discord.Forbidden:
            return await private_error(
                interaction,
                "❌ I cannot send messages in that channel.",
            )
        except discord.HTTPException:
            logger.exception("Failed to send ticket panel.")
            return await private_error(
                interaction,
                "❌ Failed to send the ticket panel.",
            )

        await interaction.response.send_message(
            f"✅ Ticket panel sent in {channel.mention}.",
            ephemeral=True,
        )

    @app_commands.command(
        name="adduser",
        description="Add a member to the current ticket.",
    )
    @app_commands.guild_only()
    async def adduser(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ):
        if not is_staff(interaction.user):
            return await private_error(interaction, "❌ Staff only.")

        if not isinstance(interaction.channel, discord.TextChannel):
            return await private_error(
                interaction,
                "Use this command inside a ticket channel.",
            )

        channel = interaction.channel

        if get_ticket_owner_id(channel) is None:
            return await private_error(
                interaction,
                "This channel does not appear to be a ticket.",
            )

        try:
            await channel.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                attach_files=True,
                embed_links=True,
                read_message_history=True,
                add_reactions=True,
            )
            await interaction.response.send_message(
                f"✅ {member.mention} has been added to this ticket.",
            )
        except discord.Forbidden:
            await private_error(interaction, "❌ I cannot edit channel permissions.")
        except discord.HTTPException:
            logger.exception("Failed to add ticket member.")
            await private_error(interaction, "❌ Failed to add the member.")

    @app_commands.command(
        name="removeuser",
        description="Remove a member's custom access to the current ticket.",
    )
    @app_commands.guild_only()
    async def removeuser(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ):
        if not is_staff(interaction.user):
            return await private_error(interaction, "❌ Staff only.")

        if not isinstance(interaction.channel, discord.TextChannel):
            return await private_error(
                interaction,
                "Use this command inside a ticket channel.",
            )

        channel = interaction.channel

        if get_ticket_owner_id(channel) is None:
            return await private_error(
                interaction,
                "This channel does not appear to be a ticket.",
            )

        owner_id = get_ticket_owner_id(channel)

        if member.id == owner_id:
            return await private_error(
                interaction,
                "You cannot remove the ticket owner. Close the ticket instead.",
            )

        try:
            await channel.set_permissions(member, overwrite=None)
            await interaction.response.send_message(
                f"✅ Removed {member.mention}'s custom ticket access.",
            )
        except discord.Forbidden:
            await private_error(interaction, "❌ I cannot edit channel permissions.")
        except discord.HTTPException:
            logger.exception("Failed to remove ticket member.")
            await private_error(interaction, "❌ Failed to remove the member.")

    @app_commands.command(
        name="ticketinfo",
        description="Show information about the current ticket.",
    )
    @app_commands.guild_only()
    async def ticketinfo(self, interaction: discord.Interaction):
        if not isinstance(interaction.channel, discord.TextChannel):
            return await private_error(
                interaction,
                "Use this command inside a ticket channel.",
            )

        channel = interaction.channel
        owner_id = get_ticket_owner_id(channel)

        if owner_id is None:
            return await private_error(
                interaction,
                "This channel does not appear to be a ticket.",
            )

        if not is_staff(interaction.user) and interaction.user.id != owner_id:
            return await private_error(
                interaction,
                "You do not have permission to view this ticket's information.",
            )

        guild = interaction.guild
        owner = guild.get_member(owner_id) if guild else None
        claimed_id = get_ticket_claimed_id(channel)
        claimed_member = guild.get_member(claimed_id) if guild and claimed_id else None

        embed = discord.Embed(
            title="🎫 Ticket Information",
            color=ORANGE,
            timestamp=channel.created_at,
        )
        embed.add_field(
            name="Channel",
            value=f"{channel.mention}\n`{channel.name}`",
            inline=False,
        )
        embed.add_field(
            name="Owner",
            value=owner.mention if owner else f"`{owner_id}`",
            inline=True,
        )
        embed.add_field(
            name="Category",
            value=get_ticket_category_name(channel),
            inline=True,
        )
        embed.add_field(
            name="Claimed By",
            value=claimed_member.mention if claimed_member else "Unclaimed",
            inline=True,
        )
        embed.add_field(
            name="Created",
            value=discord.utils.format_dt(channel.created_at, style="F"),
            inline=False,
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))

    # Persistent views keep existing ticket buttons functional after restart.
    bot.add_view(TicketPanel())
    bot.add_view(TicketControls())
    bot.add_view(TicketCloseControls())
