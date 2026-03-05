import discord
from discord.ext import commands
from discord import app_commands
import json

TICKET_CATEGORY_ID = 1389838715647692900
LOG_CHANNEL_ID = 1389842003906265098

GENERAL_ROLE = 1389824693388837035
RECRUIT_ROLE = 1432616013257773227
EXEC_ROLE = 1389824452778262589
PIREP_ROLE = 1432615867488669706
ROUTE_ROLE = 1432615814921453649


def get_ticket_number():
    try:
        with open("ticket_count.json") as f:
            data = json.load(f)
    except:
        data = {"count": 0}

    data["count"] += 1

    with open("ticket_count.json", "w") as f:
        json.dump(data, f)

    return data["count"]


class TicketDropdown(discord.ui.Select):

    def __init__(self):

        options = [
            discord.SelectOption(label="General Support", emoji="🎫"),
            discord.SelectOption(label="Recruitments", emoji="🧑‍✈️"),
            discord.SelectOption(label="Executive Team Support", emoji="👔"),
            discord.SelectOption(label="PIREP Support", emoji="📊"),
            discord.SelectOption(label="Route Support", emoji="🗺️"),
        ]

        super().__init__(
            placeholder="Select ticket category",
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        guild = interaction.guild
        user = interaction.user
        category = guild.get_channel(TICKET_CATEGORY_ID)

        number = get_ticket_number()
        ticket_name = f"ticket-{number:04}"

        role_ping = None

        if self.values[0] == "General Support":
            role_ping = guild.get_role(GENERAL_ROLE)

        if self.values[0] == "Recruitments":
            role_ping = guild.get_role(RECRUIT_ROLE)

        if self.values[0] == "Executive Team Support":
            role_ping = guild.get_role(EXEC_ROLE)

        if self.values[0] == "PIREP Support":
            role_ping = guild.get_role(PIREP_ROLE)

        if self.values[0] == "Route Support":
            role_ping = guild.get_role(ROUTE_ROLE)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            role_ping: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        channel = await guild.create_text_channel(
            name=ticket_name,
            category=category,
            overwrites=overwrites
        )

        embed = discord.Embed(
            title=f"🎫 Ticket #{number}",
            description=f"{user.mention} opened **{self.values[0]}** ticket.",
            color=discord.Color.green()
        )

        embed.add_field(name="Status", value="Open")

        await channel.send(
            content=role_ping.mention,
            embed=embed,
            view=TicketButtons()
        )

        await interaction.response.send_message(
            f"Ticket created: {channel.mention}",
            ephemeral=True
        )


class TicketPanel(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())


class TicketButtons(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", emoji="👨‍✈️", style=discord.ButtonStyle.success)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_message(
            f"Ticket claimed by {interaction.user.mention}"
        )

    @discord.ui.button(label="Lock", emoji="🔒", style=discord.ButtonStyle.secondary)
    async def lock(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.channel.set_permissions(
            interaction.guild.default_role,
            send_messages=False
        )

        await interaction.response.send_message("Ticket locked.")

    @discord.ui.button(label="Close", emoji="❌", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):

        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)

        messages = []
        async for msg in interaction.channel.history(limit=100):
            messages.append(f"{msg.author}: {msg.content}")

        transcript = "\n".join(messages)

        embed = discord.Embed(
            title="Ticket Closed",
            description=f"Closed by {interaction.user.mention}",
            color=discord.Color.red()
        )

        if log_channel:
            await log_channel.send(embed=embed)
            await log_channel.send(f"```\n{transcript}\n```")

        await interaction.channel.set_permissions(
            interaction.guild.default_role,
            view_channel=False
        )

        await interaction.response.send_message("Ticket closed.")

    @discord.ui.button(label="Reopen", emoji="🔓", style=discord.ButtonStyle.primary)
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.channel.set_permissions(
            interaction.guild.default_role,
            view_channel=True
        )

        await interaction.response.send_message("Ticket reopened.")


class Tickets(commands.Cog):

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
            title="✈️ Akasa Air Virtual Support Center",
            description="""
Need assistance with any **Akasa Air service**?

Select a category below to open a support ticket.

• General Support  
• Recruitments  
• Executive Team Support  
• PIREP Support  
• Route Support
""",
            color=discord.Color.orange()
        )

        if image:
            embed.set_image(url=image)

        await channel.send(embed=embed, view=TicketPanel())

        await interaction.response.send_message(
            f"Ticket panel created in {channel.mention}",
            ephemeral=True
        )

    @app_commands.command(name="adduser", description="Add user to ticket")
    async def adduser(self, interaction: discord.Interaction, user: discord.Member):

        await interaction.channel.set_permissions(
            user,
            view_channel=True,
            send_messages=True
        )

        await interaction.response.send_message(
            f"{user.mention} added to the ticket."
        )

    @app_commands.command(name="removeuser", description="Remove user from ticket")
    async def removeuser(self, interaction: discord.Interaction, user: discord.Member):

        await interaction.channel.set_permissions(user, overwrite=None)

        await interaction.response.send_message(
            f"{user.mention} removed from ticket."
        )


async def setup(bot):
    await bot.add_cog(Tickets(bot))
