import discord
from discord.ext import commands
from discord import app_commands

TICKET_CATEGORY_ID = 1389838715647692900  # Ticket category ID
LOG_CHANNEL_ID = 1389842003906265098     # Ticket logs channel ID
STAFF_ROLE_ID = 1389824693388837035     # Staff role ID

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_ticket(self, interaction, name):

        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.get_role(STAFF_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )

        embed = discord.Embed(
            title="🎫 Ticket Created",
            description=f"{interaction.user.mention} opened **{name}** ticket.\n\nA staff member will assist you soon.",
            color=discord.Color.green()
        )

        await channel.send(embed=embed, view=TicketControls())

        await interaction.response.send_message(
            f"✅ Ticket created: {channel.mention}",
            ephemeral=True
        )

    @discord.ui.button(label="General Support", style=discord.ButtonStyle.primary)
    async def general(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "General Support")

    @discord.ui.button(label="Recruitments", style=discord.ButtonStyle.success)
    async def recruit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Recruitments")

    @discord.ui.button(label="Executive Team Support", style=discord.ButtonStyle.secondary)
    async def executive(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Executive Support")

    @discord.ui.button(label="PIREP Support", style=discord.ButtonStyle.danger)
    async def pirep(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "PIREP Support")


class TicketControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.success)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):

        if STAFF_ROLE_ID not in [role.id for role in interaction.user.roles]:
            return await interaction.response.send_message("Staff only.", ephemeral=True)

        embed = discord.Embed(
            description=f"👨‍✈️ Ticket claimed by {interaction.user.mention}",
            color=discord.Color.blue()
        )

        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Lock", style=discord.ButtonStyle.secondary)
    async def lock(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.channel.set_permissions(
            interaction.guild.default_role,
            send_messages=False
        )

        await interaction.response.send_message("🔒 Ticket locked")

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):

        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)

        embed = discord.Embed(
            title="Ticket Closed",
            description=f"Closed by {interaction.user.mention}",
            color=discord.Color.red()
        )

        if log_channel:
            await log_channel.send(embed=embed)

        await interaction.response.send_message(
            "❌ Ticket closed. Deleting in 5 seconds..."
        )

        await discord.utils.sleep_until(discord.utils.utcnow() + discord.timedelta(seconds=5))

        await interaction.channel.delete()

    @discord.ui.button(label="Reopen", style=discord.ButtonStyle.primary)
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.channel.set_permissions(
            interaction.guild.default_role,
            send_messages=True
        )

        await interaction.response.send_message("🔓 Ticket reopened")


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ticketpanel", description="Create ticket panel")
    async def ticketpanel(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="🎫 Akasa Air Virtual Support Center",
            description="""
Welcome to the **Akasa Air Virtual Support Center!**

Need assistance with any Akasa Air service? You're in the right place!

Our dedicated <@&1389824693388837035> is here to help you quickly and efficiently.

**Please select a category below to create a ticket:**

• General Support  
• Recruitments  
• Executive Team Support  
• PIREP Support  

We’re committed to making your journey smooth and stress-free! 🌍✈️
""",
            color=discord.Color.orange()
        )

        await interaction.response.send_message(embed=embed, view=TicketView())


async def setup(bot):
    await bot.add_cog(Tickets(bot))
