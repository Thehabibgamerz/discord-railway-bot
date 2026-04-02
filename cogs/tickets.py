import discord
from discord.ext import commands
from discord import app_commands
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
import io
from datetime import datetime

TICKET_CATEGORY_ID = 1389838715647692900
LOG_CHANNEL_ID = 1389842003906265098
STAFF_ROLE = 1389824693388837035

GENERAL_ROLE = 1389824693388837035
RECRUIT_ROLE = 1432616013257773227
EXEC_ROLE = 1389824452778262589
PIREP_ROLE = 1432615867488669706
ROUTE_ROLE = 1432615814921453649


# ================= TRANSCRIPT =================

async def generate_transcript(channel: discord.TextChannel):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f"Ticket: {channel.name}", styles["Title"]))
    elements.append(Spacer(1, 10))

    async for msg in channel.history(limit=None, oldest_first=True):
        time = msg.created_at.strftime("%Y-%m-%d %H:%M")
        content = msg.content or "[No text]"
        text = f"[{time}] {msg.author}: {content}"
        elements.append(Paragraph(text, styles["Normal"]))
        elements.append(Spacer(1, 5))

    doc.build(elements)
    buffer.seek(0)
    return buffer


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
            options=options,
            custom_id="ticket_dropdown"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)

        if not category:
            return await interaction.followup.send("❌ Category not found")

        # ✅ MULTIPLE TICKETS ALLOWED (NEW)
        count = len([c for c in category.text_channels if str(interaction.user.id) in c.name])
        channel_name = f"ticket-{interaction.user.id}-{count+1}"

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

        role_map = {
            "General Support": GENERAL_ROLE,
            "Recruitments": RECRUIT_ROLE,
            "Executive Team Support": EXEC_ROLE,
            "PIREP Support": PIREP_ROLE,
            "Route Support": ROUTE_ROLE
        }

        role_ping = role_map.get(self.values[0], GENERAL_ROLE)

        embed = discord.Embed(
            title="🎫 Support Ticket",
            description=f"{interaction.user.mention}, describe your issue.\nStaff will assist you.",
            color=discord.Color.orange()
        )

        await channel.send(f"<@&{role_ping}>", embed=embed, view=TicketControls())

        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            await log_channel.send(f"🆕 {interaction.user.mention} opened {channel.mention}")

        await interaction.followup.send(f"✅ Ticket created: {channel.mention}")


# ================= PANEL =================

class TicketPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())


# ================= CONTROLS =================

class TicketControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.green, custom_id="ticket_claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):

        if STAFF_ROLE not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("❌ Staff only", ephemeral=True)

        await interaction.response.send_message(f"👨‍✈️ Claimed by {interaction.user.mention}")

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, custom_id="ticket_close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):

        if STAFF_ROLE not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("❌ Staff only", ephemeral=True)

        await interaction.response.send_message("🔒 Ticket closed", view=TicketCloseControls())


# ================= CLOSE =================

class TicketCloseControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Reopen", style=discord.ButtonStyle.green, custom_id="ticket_reopen")
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔓 Ticket reopened")

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.red, custom_id="ticket_delete")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_message("📝 Generating transcript...")

        transcript = await generate_transcript(interaction.channel)
        log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)

        if log_channel:
            file = discord.File(transcript, filename=f"{interaction.channel.name}.pdf")
            await log_channel.send(
                content=f"📄 Transcript for {interaction.channel.name}",
                file=file
            )

        await interaction.channel.delete()


# ================= COG =================

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ticketpanel")
    async def ticketpanel(self, interaction: discord.Interaction, channel: discord.TextChannel):

        embed = discord.Embed(
            title="Akasa Air Support Center",
            description="Select a category below to open a ticket.",
            color=discord.Color.orange()
        )

        await channel.send(embed=embed, view=TicketPanel())
        await interaction.response.send_message("✅ Panel sent", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Tickets(bot))
