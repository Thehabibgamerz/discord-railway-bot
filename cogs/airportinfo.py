import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os

IF_API_KEY = os.getenv("IF_API_KEY")
BASE_URL = "https://api.infiniteflight.com/public/v2"

class AirportInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="airportinfo", description="Get info about a specific airport (runways, gates, ATIS, etc.)")
    @app_commands.describe(icao="Airport ICAO code (e.g., VOBL, KJFK)")
    async def airportinfo(self, interaction: discord.Interaction, icao: str):
        icao = icao.upper()

        # Step 1: Fetch airport info from IF API
        async with aiohttp.ClientSession() as session:
            url = f"{BASE_URL}/airports/{icao}?apikey={IF_API_KEY}"
            async with session.get(url) as resp:
                if resp.status != 200:
                    await interaction.response.send_message(f"❌ Failed to fetch info for {icao} (HTTP {resp.status})", ephemeral=True)
                    return
                airport_data = await resp.json()

        if not airport_data.get("result"):
            await interaction.response.send_message(f"⚠️ No data found for {icao}", ephemeral=True)
            return

        info = airport_data["result"]

        # Runways info
        runways = info.get("runways", [])
        runway_list = "\n".join([f"{r['ident1']}/{r['ident2']} — {r['length']}m | {r['surface']}" for r in runways]) or "No runway data"

        # Gates info
        gates = info.get("gates", [])
        gate_list = ", ".join([g['name'] for g in gates]) or "No gates data"

        # Elevation
        elevation = info.get("elevation", "N/A")

        # Embed message
        embed = discord.Embed(
            title=f"🛫 Airport Info — {icao}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Elevation", value=f"{elevation} ft", inline=True)
        embed.add_field(name="Runways", value=runway_list, inline=False)
        embed.add_field(name="Gates", value=gate_list, inline=False)

        # Step 2: Try fetching ATIS
        async with aiohttp.ClientSession() as session:
            sessions_url = f"{BASE_URL}/sessions?apikey={IF_API_KEY}"
            async with session.get(sessions_url) as resp:
                if resp.status == 200:
                    sessions_data = await resp.json()
                    sessions = sessions_data.get("result", [])
                    if sessions:
                        # take first active session for demo
                        session_id = sessions[0].get("id")
                        atis_url = f"{BASE_URL}/sessions/{session_id}/airport/{icao}/atis?apikey={IF_API_KEY}"
                        async with session.get(atis_url) as atis_resp:
                            if atis_resp.status == 200:
                                atis_data = await atis_resp.json()
                                atis_text = atis_data.get("result")
                                if atis_text:
                                    embed.add_field(name="ATIS", value=f"📡 {atis_text}", inline=False)

        embed.set_footer(text="Data provided by Infinite Flight Live API")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(AirportInfo(bot))
