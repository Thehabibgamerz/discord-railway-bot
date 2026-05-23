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
    
    
# ================= HELPERS =================    
    
def is_staff(member):    
    return STAFF_ROLE in [role.id for role in member.roles]    
    
    
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
    
        # Unique ticket name    
        timestamp = datetime.utcnow().strftime("%H%M%S")    
        channel_name = f"ticket-{interaction.user.name.lower()}-{timestamp}"    
    
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
    
        embed.set_thumbnail(url=interaction.user.display_avatar.url)    
    
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
    
    
# ================= TICKET CONTROLS =================    
    
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
    
    # CLOSE BUTTON    
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
    
        # LOCK TICKET
        if interaction.channel.topic:
            try:
                owner_id = int(
                    interaction.channel.topic.replace(
                        "Ticket Owner: ",
                        ""
                    )
                )

                owner = interaction.guild.get_member(owner_id)

                if owner:
                    await interaction.channel.set_permissions(
                        owner,
                        send_messages=False,
                        add_reactions=False
                    )

            except:
                pass
    
        embed = discord.Embed(    
            title="🔒 Ticket Closed",    
            description=(    
                "This ticket has been closed.\n\n"    
                "You may reopen it if further assistance is required "    
                "or permanently delete it."    
            ),    
            color=discord.Color.red()    
        )    
    
        await interaction.response.send_message(    
            embed=embed,    
            view=TicketCloseControls()    
        )    
    
    
# ================= CLOSE CONTROLS =================    
    
class TicketCloseControls(discord.ui.View):    
    
    def __init__(self):    
        super().__init__(timeout=None)    
    
    # REOPEN    
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

        # REOPEN TICKET
        if interaction.channel.topic:
            try:
                owner_id = int(
                    interaction.channel.topic.replace(
                        "Ticket Owner: ",
                        ""
                    )
                )

                owner = interaction.guild.get_member(owner_id)

                if owner:
                    await interaction.channel.set_permissions(
                        owner,
                        send_messages=True,
                        add_reactions=True,
                        attach_files=True,
                        embed_links=True,
                        read_message_history=True
                    )

            except:
                pass
    
        embed = discord.Embed(    
            description="✅ Ticket reopened successfully.",    
            color=discord.Color.green()    
        )    
    
        await interaction.response.send_message(embed=embed)    
    
    # DELETE    
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
            "🗑️ Deleting ticket in 1 minute..."    
        )

        await asyncio.sleep(60)
    
        await interaction.channel.delete()    
    
    
# ================= COG =================    
    
class Tickets(commands.Cog):    
    
    def __init__(self, bot):    
        self.bot = bot    
    
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
