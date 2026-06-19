import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import asyncio

TICKET_CATEGORY_ID = 1389838715647692900
LOG_CHANNEL_ID = 1389842003906265098

STAFF_ROLE = 1389824693388837035

GENERAL_ROLE = 1389824693388837035
RECRUIT_ROLE = 1432616013257773227
EXEC_ROLE = 1389824452778262589
PIREP_ROLE = 1432615867488669706
ROUTE_ROLE = 1432615814921453649

CLOSED_CATEGORY_ID = None  # optional: set a category ID to move closed tickets into, or leave None

# ================= HELPERS =================

def is_staff(member):
    return STAFF_ROLE in [role.id for role in member.roles]


def get_ticket_owner_id(channel):
    if channel.topic:
        try:
            return int(channel.topic.replace("Ticket Owner: ", ""))
        except Exception:
            return None
    return None


# ================= DROPDOWN =================

class TicketDropdown(discord.ui.Select):

    def __init__(self):

        options = [
            discord.SelectOption(
                label="General Support",
                description="General help & questions",
                emoji="🎫"
            ),
            discord.SelectOption(
                label="Recruitments",
                description="Pilot applications & recruitment",
                emoji="🧑‍✈️"
            ),
            discord.SelectOption(
                label="Executive Team Support",
                description="Management & executive support",
                emoji="⭐"
            ),
            discord.SelectOption(
                label="PIREP Support",
                description="Flight report assistance",
                emoji="📋"
            ),
            discord.SelectOption(
                label="Route Support",
                description="Routes & scheduling support",
                emoji="🗺️"
            )
        ]

        super().__init__(
            placeholder="✈️ Select a support category",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_dropdown"
        )

    async def callback(self, interaction: discord.Interaction):

        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)

        if not category:
            return await interaction.response.send_message(
                "❌ Ticket category not found.",
                ephemeral=True
            )

        # Prefix per category, e.g. "Support", "Recruitment"
        category_prefix = {
            "General Support": "support",
            "Recruitments": "recruitment",
            "Executive Team Support": "exec",
            "PIREP Support": "pirep",
            "Route Support": "route"
        }
        prefix = category_prefix.get(self.values[0], "ticket")

        username = interaction.user.name.lower().replace(" ", "-")

        # Count existing tickets in this category with the same prefix
        # to generate the next sequential number (e.g. 001, 002, ...)
        existing = [
            ch for ch in category.text_channels
            if ch.name.startswith(f"{prefix}-")
        ]
        next_number = len(existing) + 1
        channel_name = f"{prefix}-{username}-{next_number:03d}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),

            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                attach_files=True,
                embed_links=True,
                read_message_history=True
            ),

            guild.get_role(STAFF_ROLE): discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_messages=True,
                read_message_history=True
            )
        }

        # Create ticket channel
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"Ticket Owner: {interaction.user.id}"
        )

        # Role ping mapping
        role_ping = GENERAL_ROLE

        if self.values[0] == "Recruitments":
            role_ping = RECRUIT_ROLE

        elif self.values[0] == "Executive Team Support":
            role_ping = EXEC_ROLE

        elif self.values[0] == "PIREP Support":
            role_ping = PIREP_ROLE

        elif self.values[0] == "Route Support":
            role_ping = ROUTE_ROLE

        # Ticket embed
        embed = discord.Embed(
            title="🎫 Support Ticket Opened",
            description=(
                f"Welcome {interaction.user.mention}!\n\n"
                f"Your support ticket has been created for:\n"
                f"**{self.values[0]}**\n\n"
                f"Please explain your issue clearly and provide all necessary details.\n\n"
                f"🔹 A staff member will assist you shortly.\n"
                f"🔹 Avoid pinging staff repeatedly.\n"
                f"🔹 Be respectful while waiting for support.\n\n"
                f"Thank you for choosing **Akasa Air Virtual** ✈️"
            ),
            color=discord.Color.orange()
        )

        embed.add_field(
            name="📂 Ticket Information",
            value=(
                f"**Opened By:** {interaction.user.mention}\n"
                f"**Category:** {self.values[0]}\n"
                f"**Created:** <t:{int(datetime.utcnow().timestamp())}:F>"
            ),
            inline=False
        )

        embed.set_footer(
            text=f"Ticket ID: {channel.id}",
            icon_url=guild.icon.url if guild.icon else None
        )

        await channel.send(
            content=f"<@&{role_ping}>",
            embed=embed,
            view=TicketControls()
        )

        # Log ticket
        log_channel = guild.get_channel(LOG_CHANNEL_ID)

        if log_channel:
            log_embed = discord.Embed(
                title="📩 Ticket Created",
                description=(
                    f"**User:** {interaction.user.mention}\n"
                    f"**Category:** {self.values[0]}\n"
                    f"**Channel:** {channel.mention}"
                ),
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )

            await log_channel.send(embed=log_embed)

        await interaction.response.send_message(
            f"✅ Your ticket has been created: {channel.mention}",
            ephemeral=True
        )


# ================= PANEL VIEW =================

class TicketPanel(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())


# ================= TICKET CONTROLS (Claim / Close) =================

class TicketControls(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    # CLAIM BUTTON
    @discord.ui.button(
        label="Claim",
        emoji="👨‍✈️",
        style=discord.ButtonStyle.green,
        custom_id="ticket_claim"
    )
    async def claim(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff members can claim tickets.",
                ephemeral=True
            )

        embed = discord.Embed(
            description=f"✅ Ticket claimed by {interaction.user.mention}",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)

    # CLOSE BUTTON -> asks for confirmation first
    @discord.ui.button(
        label="Close",
        emoji="🔒",
        style=discord.ButtonStyle.red,
        custom_id="ticket_close"
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff members can close tickets.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="⚠️ Confirm Ticket Closure",
            description="Are you sure you want to close this ticket?",
            color=discord.Color.orange()
        )

        await interaction.response.send_message(
            embed=embed,
            view=TicketCloseConfirm(),
            ephemeral=True
        )


# ================= CLOSE CONFIRMATION =================

class TicketCloseConfirm(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(
        label="Confirm Close",
        emoji="✅",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_close_confirm"
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff members can close tickets.",
                ephemeral=True
            )

        channel = interaction.channel
        owner_id = get_ticket_owner_id(channel)

        # LOCK CHANNEL — everyone (incl. ticket owner) loses send perms, staff keep theirs
        if owner_id:
            owner = interaction.guild.get_member(owner_id)
            if owner:
                await channel.set_permissions(
                    owner,
                    view_channel=True,
                    send_messages=False,
                    add_reactions=False,
                    attach_files=False,
                    embed_links=False,
                    read_message_history=True
                )

        # Also lock @everyone just in case anyone else was added to the ticket
        await channel.set_permissions(
            interaction.guild.default_role,
            view_channel=False
        )

        embed = discord.Embed(
            title="🔒 Ticket Closed",
            description=(
                f"This ticket was closed by {interaction.user.mention}.\n\n"
                "Only staff can send messages now.\n"
                "You may reopen it if further assistance is required, "
                "or permanently delete it."
            ),
            color=discord.Color.red()
        )

        # Disable the confirm/cancel buttons on the ephemeral prompt
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=interaction.message.embeds[0], view=self)

        # Post the real closed-ticket message with Reopen/Delete controls
        await channel.send(embed=embed, view=TicketCloseControls())

        # Optionally move to a "closed" category
        if CLOSED_CATEGORY_ID:
            closed_cat = interaction.guild.get_channel(CLOSED_CATEGORY_ID)
            if closed_cat:
                await channel.edit(category=closed_cat)

        # Log it
        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="🔒 Ticket Closed",
                description=(
                    f"**Closed By:** {interaction.user.mention}\n"
                    f"**Channel:** {channel.mention}"
                ),
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            await log_channel.send(embed=log_embed)

    @discord.ui.button(
        label="Cancel",
        emoji="❌",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_close_cancel"
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        for item in self.children:
            item.disabled = True

        embed = discord.Embed(
            description="❎ Ticket closure cancelled.",
            color=discord.Color.greyple()
        )
        await interaction.response.edit_message(embed=embed, view=self)


# ================= CLOSED TICKET CONTROLS (Reopen / Delete) =================

class TicketCloseControls(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Reopen",
        emoji="🔓",
        style=discord.ButtonStyle.green,
        custom_id="ticket_reopen"
    )
    async def reopen(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff members can reopen tickets.",
                ephemeral=True
            )

        channel = interaction.channel
        owner_id = get_ticket_owner_id(channel)

        if owner_id:
            owner = interaction.guild.get_member(owner_id)
            if owner:
                await channel.set_permissions(
                    owner,
                    view_channel=True,
                    send_messages=True,
                    add_reactions=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True
                )

        await channel.set_permissions(
            interaction.guild.default_role,
            view_channel=False
        )

        # Move back to the open ticket category
        category = interaction.guild.get_channel(TICKET_CATEGORY_ID)
        if category:
            await channel.edit(category=category)

        embed = discord.Embed(
            title="🔓 Ticket Reopened",
            description=f"This ticket was reopened by {interaction.user.mention}.",
            color=discord.Color.green()
        )

        # Disable buttons on the old closed message
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        await channel.send(embed=embed, view=TicketControls())

    @discord.ui.button(
        label="Delete",
        emoji="🗑️",
        style=discord.ButtonStyle.red,
        custom_id="ticket_delete"
    )
    async def delete(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff members can delete tickets.",
                ephemeral=True
            )

        await interaction.response.send_message(
            "🗑️ Deleting this ticket in 5 seconds...",
        )

        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="🗑️ Ticket Deleted",
                description=(
                    f"**Deleted By:** {interaction.user.mention}\n"
                    f"**Channel:** {interaction.channel.name}"
                ),
                color=discord.Color.dark_red(),
                timestamp=datetime.utcnow()
            )
            await log_channel.send(embed=log_embed)

        await asyncio.sleep(5)
        await interaction.channel.delete()


# ================= COG =================

class Tickets(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # ================= PERSISTENT VIEWS =================
    # Register these in your bot's setup_hook / on_ready so buttons keep
    # working after a bot restart, e.g.:
    #   self.bot.add_view(TicketPanel())
    #   self.bot.add_view(TicketControls())
    #   self.bot.add_view(TicketCloseControls())

    # ================= PANEL COMMAND =================

    @app_commands.command(
        name="ticketpanel",
        description="Send the support ticket panel"
    )
    async def ticketpanel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        image: str | None = None
    ):

        # STAFF ONLY
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff members can send the ticket panel.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="🎫 Akasa Air Virtual Support Center",
            description=(
                "Welcome to the official support center of "
                "**Akasa Air Virtual** ✈️\n\n"

                "Need assistance with recruitment, routes, "
                "PIREPs, management support, or general questions?\n\n"

                "### 📂 Available Ticket Categories\n"
                "🎫 **General Support**\n"
                "Get help with general questions or issues.\n\n"

                "🧑‍✈️ **Recruitments**\n"
                "Apply to join our airline or continue your onboarding.\n\n"

                "⭐ **Executive Team Support**\n"
                "Speak with management regarding important matters.\n\n"

                "📋 **PIREP Support**\n"
                "Get assistance with flight reports and logging.\n\n"

                "🗺️ **Route Support**\n"
                "Request route information or report route issues.\n\n"

                "### ⚠️ Before Opening a Ticket\n"
                "• Explain your issue clearly.\n"
                "• Be respectful to staff members.\n"
                "• Avoid opening unnecessary tickets.\n\n"

                "Select a category below to continue."
            ),
            color=discord.Color.orange()
        )

        embed.set_footer(
            text="Akasa Air Virtual Support System",
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )

        if image:
            embed.set_image(url=image)

        await channel.send(
            embed=embed,
            view=TicketPanel()
        )

        await interaction.response.send_message(
            f"✅ Ticket panel sent in {channel.mention}",
            ephemeral=True
        )

    # ================= ADD USER =================

    @app_commands.command(
        name="adduser",
        description="Add a user to the ticket"
    )
    async def adduser(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):

        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Staff only.",
                ephemeral=True
            )

        await interaction.channel.set_permissions(
            member,
            view_channel=True,
            send_messages=True,
            attach_files=True,
            read_message_history=True
        )

        await interaction.response.send_message(
            f"✅ {member.mention} added to the ticket."
        )

    # ================= REMOVE USER =================

    @app_commands.command(
        name="removeuser",
        description="Remove a user from the ticket"
    )
    async def removeuser(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):

        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Staff only.",
                ephemeral=True
            )

        await interaction.channel.set_permissions(
            member,
            overwrite=None
        )

        await interaction.response.send_message(
            f"❌ {member.mention} removed from the ticket."
        )


async def setup(bot):
    await bot.add_cog(Tickets(bot))
    # Register persistent views so buttons survive bot restarts
    bot.add_view(TicketPanel())
    bot.add_view(TicketControls())
    bot.add_view(TicketCloseControls())
