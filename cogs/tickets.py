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
  
  
# ================= DROPDOWN =================  
  
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
        channel_name = f"ticket-{username}"  
  
        existing = discord.utils.get(category.text_channels, name=channel_name)  
  
        if existing:  
            await interaction.response.send_message(  
                f"You already have a ticket: {existing.mention}",  
                ephemeral=True  
            )  
            return  
  
        overwrites = {  
            guild.default_role: discord.PermissionOverwrite(view_channel=False),  
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),  
            guild.get_role(STAFF_ROLE): discord.PermissionOverwrite(view_channel=True)  
        }  
  
        channel = await guild.create_text_channel(  
            name=channel_name,  
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
            description=f"{interaction.user.mention} please describe your issue.\nStaff will assist you shortly.",  
            color=discord.Color.orange()  
        )  
  
        await channel.send(  
            f"<@&{role_ping}>",  
            embed=embed,  
            view=TicketControls()  
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
  
  
# ================= PANEL VIEW =================  
  
class TicketPanel(discord.ui.View):  
  
    def __init__(self):  
        super().__init__(timeout=None)  
        self.add_item(TicketDropdown())  
  
  
# ================= TICKET BUTTONS =================  
  
class TicketControls(discord.ui.View):  
  
    def __init__(self):  
        super().__init__(timeout=None)  
  
    @discord.ui.button(  
        label="Claim",  
        style=discord.ButtonStyle.green,  
        custom_id="ticket_claim"  
    )  
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):  
  
        if STAFF_ROLE not in [role.id for role in interaction.user.roles]:  
            await interaction.response.send_message(  
                "❌ Only staff can claim tickets.",  
                ephemeral=True  
            )  
            return  
  
        embed = discord.Embed(  
            description=f"👨‍✈️ Ticket claimed by {interaction.user.mention}",  
            color=discord.Color.green()  
        )  
  
        await interaction.response.send_message(embed=embed)  
  
    @discord.ui.button(  
        label="Close",  
        style=discord.ButtonStyle.red,  
        custom_id="ticket_close"  
    )  
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):  
  
        if STAFF_ROLE not in [role.id for role in interaction.user.roles]:  
            await interaction.response.send_message(  
                "❌ Only staff can close tickets.",  
                ephemeral=True  
            )  
            return  
  
        embed = discord.Embed(  
            title="Ticket Closed",  
            description="Use the buttons below to reopen or delete.",  
            color=discord.Color.red()  
        )  
  
        await interaction.response.send_message(  
            embed=embed,  
            view=TicketCloseControls()  
        )  
  
  
# ================= CLOSE OPTIONS =================  
  
class TicketCloseControls(discord.ui.View):  
  
    def __init__(self):  
        super().__init__(timeout=None)  
  
    @discord.ui.button(  
        label="Reopen",  
        style=discord.ButtonStyle.green,  
        custom_id="ticket_reopen"  
    )  
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):  
  
        embed = discord.Embed(  
            description="🔓 Ticket reopened.",  
            color=discord.Color.green()  
        )  
  
        await interaction.response.send_message(embed=embed)  
  
    @discord.ui.button(  
        label="Delete",  
        style=discord.ButtonStyle.red,  
        custom_id="ticket_delete"  
    )  
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):  
  
        await interaction.response.send_message("Deleting ticket...")  
        await interaction.channel.delete()  
  
  
# ================= COG =================  
  
class Tickets(commands.Cog):  
  
    def __init__(self, bot):  
        self.bot = bot  
  
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
                "Need assistance with any Akasa Air service?\n"  
                "Our dedicated <@&1389824693388837035> is here to help you quickly.\n\n"  
                "**Select a category below to create a ticket:**\n\n"  
                "• General Support\n"  
                "• Recruitments\n"  
                "• Executive Team Support\n"  
                "• PIREP Support\n"  
                "• Route Support\n\n"  
                "We’re committed to making your journey smooth! 🌍✈️"  
            ),  
            color=discord.Color.orange()  
        )  
  
        if image:  
            embed.set_image(url=image)  
  
        await channel.send(embed=embed, view=TicketPanel())  
  
        await interaction.response.send_message(  
            "✅ Ticket panel sent successfully.",  
            ephemeral=True  
        )  
  
    # Add user  
    @app_commands.command(name="adduser", description="Add user to ticket")  
    async def adduser(self, interaction: discord.Interaction, member: discord.Member):  
  
        await interaction.channel.set_permissions(  
            member,  
            view_channel=True,  
            send_messages=True  
        )  
  
        embed = discord.Embed(  
            description=f"✅ {member.mention} added to the ticket.",  
            color=discord.Color.green()  
        )  
  
        await interaction.response.send_message(embed=embed)  
  
    # Remove user  
    @app_commands.command(name="removeuser", description="Remove user from ticket")  
    async def removeuser(self, interaction: discord.Interaction, member: discord.Member):  
  
        await interaction.channel.set_permissions(member, overwrite=None)  
  
        embed = discord.Embed(  
            description=f"❌ {member.mention} removed from the ticket.",  
            color=discord.Color.red()  
        )  
  
        await interaction.response.send_message(embed=embed)  
  
  
async def setup(bot):  
    await bot.add_cog(Tickets(bot))  
