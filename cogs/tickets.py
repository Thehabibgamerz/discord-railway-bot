import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View, Select
from datetime import datetime

# ===== CONFIG =====

TICKET_CATEGORY_ID = 1389838715647692900
LOG_CHANNEL_ID = 1389842003906265098

STAFF_ROLE = 1389824693388837035

GENERAL_ROLE = 1389824693388837035
RECRUIT_ROLE = 1432616013257773227
EXEC_ROLE = 1389824452778262589
PIREP_ROLE = 1432615867488669706
ROUTE_ROLE = 1432615814921453649


# ===== CLOSE VIEW =====

class CloseView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):

        if STAFF_ROLE not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message(
                "Only staff can close tickets.", ephemeral=True
            )
            return

        await interaction.channel.set_permissions(
            interaction.channel.guild.default_role,
            send_messages=False
        )

        await interaction.response.send_message(
            "Ticket closed.", view=ClosedButtons()
        )


# ===== CLOSED BUTTONS =====

class ClosedButtons(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Reopen", style=discord.ButtonStyle.green, emoji="🔓")
    async def reopen(self, interaction: discord.Interaction, button: Button):

        if STAFF_ROLE not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message(
                "Only staff can reopen tickets.", ephemeral=True
            )
            return

        await interaction.channel.set_permissions(
            interaction.channel.guild.default_role,
            send_messages=True
        )

        await interaction.response.send_message(
            "Ticket reopened.", view=CloseView()
        )

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.gray, emoji="🗑️")
    async def delete(self, interaction: discord.Interaction, button: Button):

        if STAFF_ROLE not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message(
                "Only staff can delete tickets.", ephemeral=True
            )
            return

        log = interaction.guild.get_channel(LOG_CHANNEL_ID)

        if log:
            embed = discord.Embed(
                title="Ticket Deleted",
                description=f"Deleted by {interaction.user.mention}",
                color=discord.Color.red()
            )
            await log.send(embed=embed)

        await interaction.response.send_message("Deleting ticket...")
        await interaction.channel.delete()


# ===== CLAIM BUTTON =====

class ClaimButton(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.blurple, emoji="👨‍✈️")
    async def claim(self, interaction: discord.Interaction, button: Button):

        if STAFF_ROLE not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message(
                "Only staff can claim tickets.", ephemeral=True
            )
            return

        embed = discord.Embed(
            description=f"👨‍✈️ Ticket claimed by {interaction.user.mention}",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed)


# ===== DROPDOWN =====

class TicketDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="General Support"),
            discord.SelectOption(label="Recruitments"),
            discord.SelectOption(label="Executive Team Support"),
            discord.SelectOption(label="PIREP Support"),
            discord.SelectOption(label="Route Support"),
        ]

        super().__init__(
            placeholder="Select ticket category",
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)

        role_map = {
            "General Support": GENERAL_ROLE,
            "Recruitments": RECRUIT_ROLE,
            "Executive Team Support": EXEC_ROLE,
            "PIREP Support": PIREP_ROLE,
            "Route Support": ROUTE_ROLE
        }

        role_id = role_map[self.values[0]]

        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category
        )

        await channel.set_permissions(interaction.user, read_messages=True, send_messages=True)

        role = guild.get_role(role_id)

        embed = discord.Embed(
            title="🎫 Akasa Air Support Ticket",
            description=f"""
User: {interaction.user.mention}
Category: **{self.values[0]}**
Created: <t:{int(datetime.utcnow().timestamp())}:F>

A staff member will assist you shortly.
""",
            color=discord.Color.blue()
        )

        await channel.send(role.mention)

        await channel.send(
            content=interaction.user.mention,
            embed=embed,
            view=ClaimButton()
        )

        await channel.send(view=CloseView())

        await interaction.response.send_message(
            f"Ticket created: {channel.mention}",
            ephemeral=True
        )


class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())


# ===== COG =====

class Ticket(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ticketpanel", description="Create ticket panel")
    async def ticketpanel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        image: str = None
    ):

        embed = discord.Embed(
            title="Akasa Air Virtual Support Center",
            description="""
Welcome to the **Akasa Air Virtual Support Center!**

Need assistance with any Akasa Air service? You're in the right place!

Our dedicated support team is here to help.

Select a category below to create a ticket.
""",
            color=discord.Color.orange()
        )

        if image:
            embed.set_image(url=image)

        await channel.send(embed=embed, view=TicketView())

        await interaction.response.send_message(
            "Ticket panel created.",
            ephemeral=True
        )

    # ===== ADD USER =====

    @app_commands.command(name="add", description="Add user to ticket")
    async def add(self, interaction: discord.Interaction, user: discord.Member):

        await interaction.channel.set_permissions(user, read_messages=True, send_messages=True)

        await interaction.response.send_message(
            f"{user.mention} added to ticket."
        )

    # ===== REMOVE USER =====

    @app_commands.command(name="remove", description="Remove user from ticket")
    async def remove(self, interaction: discord.Interaction, user: discord.Member):

        await interaction.channel.set_permissions(user, overwrite=None)

        await interaction.response.send_message(
            f"{user.mention} removed from ticket."
        )


async def setup(bot):
    await bot.add_cog(Ticket(bot))
