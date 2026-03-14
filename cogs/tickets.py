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


class TicketDropdown(discord.ui.Select):

    def __init__(self):

        options = [
            discord.SelectOption(label="General Support", emoji="🎫"),
            discord.SelectOption(label="Recruitments", emoji="🧑‍✈️"),
            discord.SelectOption(label="Executive Team Support", emoji="⭐"),
            discord.SelectOption(label="PIREP Support", emoji="📋"),
            discord.SelectOption(label="Route Support", emoji="🗺️")
        ]

        super().__init__(
            placeholder="Select ticket category...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_dropdown"
        )

    async def callback(self, interaction: discord.Interaction):

        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)

        name = interaction.user.name.lower().replace(" ", "-")

        channel = discord.utils.get(
            category.text_channels,
            name=f"ticket-{name}"
        )

        if channel:
            await interaction.response.send_message(
                f"You already have a ticket: {channel.mention}",
                ephemeral=True
            )
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_role(STAFF_ROLE): discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        channel = await guild.create_text_channel(
            name=f"ticket-{name}",
            category=category,
            overwrites=overwrites
        )

        role_ping = None
        label = self.values[0]

        if label == "General Support":
            role_ping = GENERAL_ROLE
        elif label == "Recruitments":
            role_ping = RECRUIT_ROLE
        elif label == "Executive Team Support":
            role_ping = EXEC_ROLE
        elif label == "PIREP Support":
            role_ping = PIREP_ROLE
        elif label == "Route Support":
            role_ping = ROUTE_ROLE

        embed = discord.Embed(
            title="🎫 Support Ticket",
            description=(
                f"Hello {interaction.user.mention},\n\n"
                f"Our support team will assist you shortly.\n"
                f"Please describe your issue clearly."
            ),
            color=discord.Color.orange()
        )

        view = TicketControls()

        await channel.send(
            f"<@&{role_ping}>",
            embed=embed,
            view=view
        )

        await interaction.response.send_message(
            f"✅ Ticket created: {channel.mention}",
            ephemeral=True
        )


class TicketPanel(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())


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

        await interaction.response.send_message(
            f"✅ Ticket claimed by {interaction.user.mention}"
        )

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
            description="You can reopen or delete this ticket.",
            color=discord.Color.red()
        )

        await interaction.response.send_message(
            embed=embed,
            view=TicketCloseControls()
        )


class TicketCloseControls(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Reopen", style=discord.ButtonStyle.green, custom_id="reopen_ticket")
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_message(
            "✅ Ticket reopened."
        )

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.red, custom_id="delete_ticket")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_message("Deleting ticket...")
        await interaction.channel.delete()


class Tickets(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ticketpanel", description="Send ticket panel")
    async def ticketpanel(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="Akasa Air Virtual Support Center",
            description=(
                "Need assistance with any Akasa Air service?\n\n"
                "Select a category below to create a ticket."
            ),
            color=discord.Color.orange()
        )

        view = TicketPanel()

        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(Tickets(bot))
