import discord
from discord.ext import commands
from discord import app_commands

TICKET_CATEGORY_ID = 1389838715647692900
LOG_CHANNEL_ID = 1389842003906265098

STAFF_ROLE = 1389824693388837035

GENERAL_ROLE = 1389824693388837035
RECRUIT_ROLE = 1432616013257773227
EXEC_ROLE = 1389824452778262589
PIREP_ROLE = 1432615867488669706
ROUTE_ROLE = 1432615814921453649


# Dropdown
class TicketDropdown(discord.ui.Select):

    def __init__(self):

        options = [
            discord.SelectOption(label="General Support", emoji="🎫"),
            discord.SelectOption(label="Recruitments", emoji="🧑‍✈️"),
            discord.SelectOption(label="Executive Team Support", emoji="⭐"),
            discord.SelectOption(label="PIREP Support", emoji="📋"),
            discord.SelectOption(label="Route Support", emoji="🗺️"),
        ]

        super().__init__(
            placeholder="Select ticket category",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_dropdown"
        )

    async def callback(self, interaction: discord.Interaction):

        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)

        username = interaction.user.name.lower().replace(" ", "-")
        ticket_name = f"ticket-{username}"

        existing = discord.utils.get(category.text_channels, name=ticket_name)

        if existing:
            await interaction.response.send_message(
                f"You already have a ticket: {existing.mention}",
                ephemeral=True
            )
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_role(STAFF_ROLE): discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        channel = await guild.create_text_channel(
            name=ticket_name,
            category=category,
            overwrites=overwrites
        )

        role_ping = GENERAL_ROLE

        if self.values[0] == "Recruitments":
            role_ping = RECRUIT_ROLE
        elif self.values[0] == "Executive Team Support":
            role_ping = EXEC_ROLE
        elif self.values[0] == "PIREP Support":
            role_ping = PIREP_ROLE
        elif self.values[0] == "Route Support":
            role_ping = ROUTE_ROLE

        embed = discord.Embed(
            title="🎫 Support Ticket",
            description=f"{interaction.user.mention}, please describe your issue. Staff will assist you shortly.",
            color=discord.Color.orange()
        )

        view = TicketControls()

        await channel.send(
            f"<@&{role_ping}>",
            embed=embed,
            view=view
        )

        log_channel = guild.get_channel(LOG_CHANNEL_ID)

        if log_channel:
            log = discord.Embed(
                title="Ticket Created",
                description=f"{interaction.user.mention} opened {channel.mention}",
                color=discord.Color.green()
            )
            await log_channel.send(embed=log)

        await interaction.response.send_message(
            f"✅ Ticket created: {channel.mention}",
            ephemeral=True
        )


class TicketPanel(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())


# Ticket buttons
class TicketControls(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.green, custom_id="claim_ticket")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):

        if STAFF_ROLE not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message(
                "Only staff can claim tickets.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            description=f"👨‍✈️ Ticket claimed by {interaction.user.mention}",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):

        if STAFF_ROLE not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message(
                "Only staff can close tickets.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Ticket Closed",
            description="You can reopen or delete the ticket.",
            color=discord.Color.red()
        )

        await interaction.response.send_message(
            embed=embed,
            view=TicketCloseControls()
        )


# Close options
class TicketCloseControls(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Reopen", style=discord.ButtonStyle.green, custom_id="reopen_ticket")
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):

        embed = discord.Embed(
            description="🔓 Ticket reopened.",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.red, custom_id="delete_ticket")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_message("Deleting ticket...")
        await interaction.channel.delete()


class Tickets(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # Send ticket panel
    @app_commands.command(name="ticketpanel", description="Send the ticket panel")
    async def ticketpanel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        image: str | None = None
    ):

        embed = discord.Embed(
            title="Welcome to the Akasa Air Virtual Support Center!",
            description=(
                "Need assistance with any Akasa Air service? You're in the right place!\n"
                "Our dedicated <@&1389824693388837035> is here to help you quickly and efficiently.\n\n"
                "**Please select a category below to create a ticket:**\n\n"
                "• General Support\n"
                "• Recruitments\n"
                "• Executive Team Support\n"
                "• PIREP Support\n"
                "• Route Support\n\n"
                "We’re committed to making your journey smooth and stress-free! 🌍✈️"
            ),
            color=discord.Color.orange()
        )

        if image:
            embed.set_image(url=image)

        await channel.send(embed=embed, view=TicketPanel())

        await interaction.response.send_message(
            "✅ Ticket panel sent.",
            ephemeral=True
        )

    # Add user
    @app_commands.command(name="adduser", description="Add a user to this ticket")
    async def adduser(self, interaction: discord.Interaction, member: discord.Member):

        if STAFF_ROLE not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message(
                "❌ Only staff can use this command.",
                ephemeral=True
            )
            return

        await interaction.channel.set_permissions(
            member,
            view_channel=True,
            send_messages=True
        )

        embed = discord.Embed(
            title="User Added",
            description=f"{member.mention} has been added to the ticket.",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)

    # Remove user
    @app_commands.command(name="removeuser", description="Remove a user from this ticket")
    async def removeuser(self, interaction: discord.Interaction, member: discord.Member):

        if STAFF_ROLE not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message(
                "❌ Only staff can use this command.",
                ephemeral=True
            )
            return

        await interaction.channel.set_permissions(member, overwrite=None)

        embed = discord.Embed(
            title="User Removed",
            description=f"{member.mention} has been removed from the ticket.",
            color=discord.Color.red()
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Tickets(bot))
