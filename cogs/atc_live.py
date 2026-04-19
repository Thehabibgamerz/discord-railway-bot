import discord
from discord.ext import commands
from discord import app_commands
import aiohttp

API_KEY = "tephscpkg4qe7xxkrfwvo9qrteksdj0l"

# Expert Server Session ID
# (can also be auto-fetched later)
EXPERT_SESSION_ID = "e14cde8d-2e22-4f4f-b8d3-b6e1f6f4f5b1"


class ATCLive(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_world_status(self):
        url = f"https://api.infiniteflight.com/public/v2/sessions/{EXPERT_SESSION_ID}/world?apikey={API_KEY}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()

    @app_commands.command(
        name="atc_live",
        description="Show active ATC airports on Expert Server"
    )
    async def atc_live(self, interaction: discord.Interaction):

        await interaction.response.defer()

        data = await self.fetch_world_status()

        if not data or data.get("errorCode") != 0:
            return await interaction.followup.send(
                "❌ Failed to fetch Infinite Flight ATC data."
            )

        airports = data.get("result", [])

        if not airports:
            return await interaction.followup.send(
                "❌ No active ATC airports found."
            )

        # Sort by inbound + outbound traffic
        airports.sort(
            key=lambda x: x.get("inboundFlightsCount", 0) + x.get("outboundFlightsCount", 0),
            reverse=True
        )

        top_airports = airports[:5]

        embed = discord.Embed(
            title="✈️ Active ATC Frequencies — Expert Server",
            description="Live Infinite Flight Expert Server ATC Status",
            color=discord.Color.orange()
        )

        for airport in top_airports:
            icao = airport.get("airportIcao", "Unknown")
            inbound = airport.get("inboundFlightsCount", 0)
            outbound = airport.get("outboundFlightsCount", 0)
            total = inbound + outbound

            if total >= 150:
                traffic = "🔴 Heavy Traffic"
            elif total >= 50:
                traffic = "🟡 Moderate Traffic"
            else:
                traffic = "🟢 Low Traffic"

            value = (
                f"📥 Inbound: **{inbound}**\n"
                f"📤 Outbound: **{outbound}**\n"
                f"📊 Status: {traffic}"
            )

            embed.add_field(
                name=f"🛫 {icao}",
                value=value,
                inline=True
            )

        embed.set_footer(
            text="Powered by Infinite Flight Live API"
        )

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ATCLive(bot))
