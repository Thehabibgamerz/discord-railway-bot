import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
import aiohttp
import os

IF_API_KEY = os.getenv("IF_API_KEY")
BASE_URL = "https://api.infiniteflight.com/public/v2"

IFATC_ROLE_ID_DISCORD = 1389833550957641840  # Discord role to assign

IFATC_MEMBER_ROLE_ID = 64  # Infinite Flight role ID meaning "IFATC Members"

ATC_RANKS = {
    0: "Observer",
    1: "ATC Trainee",
    2: "ATC Apprentice",
    3: "ATC Specialist",
    4: "ATC Officer",
    5: "ATC Supervisor",
    6: "ATC Recruiter",
    7: "ATC Manager"
}

verified_users = set()  # simple memory storage


def format_flight_time(minutes):
    """Convert flightTime (minutes) into a readable Xh Ym string."""
    if not isinstance(minutes, (int, float)):
        return "N/A"
    total_minutes = int(minutes)
    hours, mins = divmod(total_minutes, 60)
    return f"{hours}h {mins}m"


# ================= MODAL =================

class VerifyModal(Modal):
    def __init__(self):
        super().__init__(title="IFC Verification")

        self.username = TextInput(
            label="Infinite Flight Username",
            placeholder="Enter your IFC username...",
            required=True
        )
        self.add_item(self.username)

    async def on_submit(self, interaction: discord.Interaction):

        user_id = interaction.user.id

        # 🔒 Prevent re-verification
        if user_id in verified_users:
            return await interaction.response.send_message(
                "⚠️ You are already verified.",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        # Confirmed endpoint: POST /users with discourseNames in the body
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{BASE_URL}/users?apikey={IF_API_KEY}",
                    json={"discourseNames": [self.username.value]}
                ) as resp:
                    if resp.status == 401:
                        return await interaction.followup.send("❌ Invalid API key.", ephemeral=True)
                    elif resp.status != 200:
                        return await interaction.followup.send(
                            f"❌ API error (HTTP {resp.status}).", ephemeral=True
                        )
                    data = await resp.json()
            except Exception as e:
                return await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

        results = data.get("result", [])

        if not results:
            return await interaction.followup.send(
                "❌ Username not found. Make sure it's your exact Infinite Flight Community username.",
                ephemeral=True
            )

        user_data = results[0]
        roles = user_data.get("roles", [])

        is_ifatc = IFATC_MEMBER_ROLE_ID in roles

        # Build the stats embed regardless of IFATC status — show details either way
        grade = user_data.get("grade", "N/A")
        flight_time = format_flight_time(user_data.get("flightTime"))
        online_flights = user_data.get("onlineFlights", "N/A")
        landing_count = user_data.get("landingCount", "N/A")
        violations = user_data.get("violations", "N/A")
        xp = user_data.get("xp", "N/A")
        atc_operations = user_data.get("atcOperations", "N/A")
        atc_rank_id = user_data.get("atcRank")
        atc_rank = ATC_RANKS.get(atc_rank_id, "N/A") if atc_rank_id is not None else "N/A"
        violation_levels = user_data.get("violationCountByLevel", {})

        embed = discord.Embed(
            title=f"✅ Verified — {self.username.value}",
            color=discord.Color.green()
        )

        embed.add_field(name="📊 Grade", value=str(grade), inline=True)
        embed.add_field(name="⏱️ Flight Time", value=flight_time, inline=True)
        embed.add_field(name="✈️ Online Flights", value=str(online_flights), inline=True)

        embed.add_field(name="🛬 Landings", value=str(landing_count), inline=True)
        embed.add_field(name="⭐ XP", value=str(xp), inline=True)
        embed.add_field(
            name="⚠️ Violations",
            value=(
                f"{violations} total "
                f"(L1: {violation_levels.get('level1', 0)}, "
                f"L2: {violation_levels.get('level2', 0)}, "
                f"L3: {violation_levels.get('level3', 0)})"
            ),
            inline=True
        )

        if is_ifatc:
            embed.add_field(name="🎖️ ATC Operations", value=str(atc_operations), inline=True)
            embed.add_field(name="🎖️ ATC Rank", value=atc_rank, inline=True)

        role = None
        if is_ifatc:
            role = interaction.guild.get_role(IFATC_ROLE_ID_DISCORD)
            if not role:
                embed.add_field(
                    name="⚠️ Note", value="IFATC role not found on this server — contact staff.", inline=False
                )
            else:
                try:
                    await interaction.user.add_roles(role, reason="IFC verification — confirmed IFATC member")
                    embed.add_field(name="🎖️ Role Assigned", value=role.mention, inline=False)
                except discord.Forbidden:
                    embed.add_field(
                        name="⚠️ Note",
                        value="Couldn't assign the IFATC role — check the bot's role position/permissions.",
                        inline=False
                    )
        else:
            embed.add_field(
                name="ℹ️ IFATC Status",
                value="Not currently an IFATC member — no role assigned.",
                inline=False
            )

        embed.set_footer(text="AkasaAirVirtual • Infinite Flight Verification")

        # Save verified
        verified_users.add(user_id)

        await interaction.followup.send(embed=embed, ephemeral=True)


# ================= VIEW =================

class VerifyView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify", emoji="✅", style=discord.ButtonStyle.success, custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(VerifyModal())


# ================= COG =================

class Verify(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="verifypanel", description="Send verification panel")
    async def verifypanel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):

        embed = discord.Embed(
            title="🔐 IFC Verification",
            description=(
                "Verify your Infinite Flight account.\n\n"
                "Click the button below and enter your IFC username.\n\n"
                "🎖️ IFATC members will automatically receive the role."
            ),
            color=discord.Color.orange()
        )

        view = VerifyView()

        await channel.send(embed=embed, view=view)

        await interaction.response.send_message(
            f"✅ Verification panel sent to {channel.mention}",
            ephemeral=True
        )


# ================= SETUP =================

async def setup(bot):
    await bot.add_cog(Verify(bot))
    bot.add_view(VerifyView())
