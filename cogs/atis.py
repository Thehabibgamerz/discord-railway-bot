import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os

# ================= CONFIG =================

IF_API_KEY = os.getenv("IF_API_KEY")
BASE_URL = "https://api.infiniteflight.com/public/v2"

SERVER_MAP = {
    "Casual": "casual",
    "Training": "training",
    "Expert": "expert"
}

# ==========================================


class ATIS(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # ================= GET SESSION =================

    async def get_session_id(self, server_key):

        async with aiohttp.ClientSession() as session:

            async with session.get(
                f"{BASE_URL}/sessions?apikey={IF_API_KEY}"
            ) as resp:

                if resp.status != 200:
                    return None

                data = await resp.json()

                for s in data.get("result", []):

                    if server_key.lower() in s.get("name", "").lower():
                        return s.get("id")

        return None

    # ================= MAIN COMMAND =================

    @app_commands.command(
        name="atis",
        description="Get live airport information"
    )
    @app_commands.describe(
        airport="Airport ICAO Code"
    )
    async def atis(
        self,
        interaction: discord.Interaction,
        airport: str
    ):

        airport = airport.upper()

        # ================= SERVER SELECT =================

        class ServerSelect(discord.ui.Select):

            def __init__(self, cog):

                self.cog = cog

                options = [
                    discord.SelectOption(
                        label="Casual",
                        emoji="🟢"
                    ),
                    discord.SelectOption(
                        label="Training",
                        emoji="🟡"
                    ),
                    discord.SelectOption(
                        label="Expert",
                        emoji="🔴"
                    )
                ]

                super().__init__(
                    placeholder="Select Infinite Flight Server",
                    min_values=1,
                    max_values=1,
                    options=options,
                    custom_id="atis_server_select"
                )

            async def callback(self, select_interaction: discord.Interaction):

                await select_interaction.response.defer(ephemeral=True)

                server_choice = self.values[0]
                server_key = SERVER_MAP[server_choice]

                # ================= GET SESSION =================

                session_id = await self.cog.get_session_id(server_key)

                if not session_id:
                    return await select_interaction.followup.send(
                        "❌ Failed to get server session.",
                        ephemeral=True
                    )

                # ================= FETCH ATIS =================

                atis_url = (
                    f"{BASE_URL}/sessions/"
                    f"{session_id}/airport/"
                    f"{airport}/atis?apikey={IF_API_KEY}"
                )

                # ================= FETCH AIRPORT STATUS =================

                airport_url = (
                    f"{BASE_URL}/sessions/"
                    f"{session_id}/airport/{airport}"
                    f"?apikey={IF_API_KEY}"
                )

                async with aiohttp.ClientSession() as session:

                    # ---------- ATIS ----------

                    try:

                        async with session.get(atis_url) as resp:

                            if resp.status != 200:

                                return await select_interaction.followup.send(
                                    f"❌ Failed to fetch ATIS.\nHTTP {resp.status}",
                                    ephemeral=True
                                )

                            atis_data = await resp.json()

                    except Exception as e:

                        return await select_interaction.followup.send(
                            f"❌ API Error:\n{e}",
                            ephemeral=True
                        )

                    # ---------- AIRPORT INFO ----------

                    try:

                        async with session.get(airport_url) as resp:

                            airport_data = await resp.json()

                    except:
                        airport_data = {}

                # ================= PARSE DATA =================

                atis_text = atis_data.get("result")

                if not atis_text:

                    atis_text = "No active ATIS available."

                result = airport_data.get("result", {})

                inbound = result.get("inboundFlightsCount", "Unknown")
                outbound = result.get("outboundFlightsCount", "Unknown")

                atc_freqs = []

                for freq in result.get("frequencies", []):

                    freq_type = freq.get("type", "Unknown")
                    value = freq.get("frequencyMHz", "N/A")

                    atc_freqs.append(
                        f"• {freq_type}: {value}"
                    )

                freq_text = (
                    "\n".join(atc_freqs)
                    if atc_freqs else
                    "No active ATC"
                )

                # ================= EMBED =================

                embed = discord.Embed(
                    title=f"📡 {airport} Airport Information",
                    color=discord.Color.orange()
                )

                embed.add_field(
                    name="🌐 Server",
                    value=server_choice,
                    inline=True
                )

                embed.add_field(
                    name="🛬 Inbound Flights",
                    value=str(inbound),
                    inline=True
                )

                embed.add_field(
                    name="🛫 Outbound Flights",
                    value=str(outbound),
                    inline=True
                )

                embed.add_field(
                    name="🎧 Active Frequencies",
                    value=freq_text,
                    inline=False
                )

                embed.add_field(
                    name="📡 ATIS",
                    value=f"```{atis_text[:1000]}```",
                    inline=False
                )

                embed.set_footer(
                    text="Akasa Air Virtual • Infinite Flight"
                )

                await select_interaction.followup.send(
                    embed=embed,
                    ephemeral=True
                )

        # ================= VIEW =================

        class ServerView(discord.ui.View):

            def __init__(self, cog):

                super().__init__(timeout=120)

                self.add_item(ServerSelect(cog))

        # ================= SEND PANEL =================

        embed = discord.Embed(
            title="📡 Infinite Flight ATIS",
            description=(
                f"Select a server below to view live airport "
                f"information for **{airport}**.\n\n"
                f"Includes:\n"
                f"• Live ATIS\n"
                f"• Active ATC Frequencies\n"
                f"• Inbound Flights\n"
                f"• Outbound Flights\n"
                f"• Airport Status"
            ),
            color=discord.Color.orange()
        )

        await interaction.response.send_message(
            embed=embed,
            view=ServerView(self),
            ephemeral=True
        )


# ================= SETUP =================

async def setup(bot):
    await bot.add_cog(ATIS(bot))
