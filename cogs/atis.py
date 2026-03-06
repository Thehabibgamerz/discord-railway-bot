import discord
from discord.ext import commands
from discord import app_commands
import aiohttp

# Replace with your actual Infinite Flight Live API key
IF_API_KEY = "tephscpkg4qe7xxkrfwvo9qrteksdj0l"
BASE_URL = "https://api.infiniteflight.com/public/v2/sessions/{sessionId}/airport/{airportIcao}/atis"

# Map friendly names to possible session names/IDs later
SERVER_MAP = {
    "Casual": "casual",
    "Training": "training",
    "Expert": "expert"
}

class ATIS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="atis", description="Get live ATIS info for an airport on Infinite Flight")
    @app_commands.describe(
        server="Choose a server (Casual, Training, Expert)",
        airport="Airport ICAO code"
    )
    async def atis(
        self,
        interaction: discord.Interaction,
        server: str,
        airport: str
    ):
        server_key = SERVER_MAP.get(server)
        if not server_key:
            await interaction.response.send_message("❌ Invalid server selection.", ephemeral=True)
            return

        # Step 1: Get all active sessions from IF Live API
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/sessions?apikey={IF_API_KEY}") as resp:
                if resp.status != 200:
                    await interaction.response.send_message("⚠️ Failed to fetch sessions.", ephemeral=True)
                    return
                data = await resp.json()

        sessions = data.get("result", [])
        if not sessions:
            await interaction.response.send_message("⚠️ No active sessions found.", ephemeral=True)
            return

        # Step 2: Find session ID that matches the server name
        session_id = None
        for s in sessions:
            # Session JSON usually contains "sessionName" or similar
            # Here we check by name if it matches the friendly server key.
            if server_key.lower() in s.get("name", "").lower():
                session_id = s.get("id")
                break

        if not session_id:
            await interaction.response.send_message(
                f"⚠️ Could not find a session for {server} server.", ephemeral=True
            )
            return

        # Step 3: Fetch ATIS for the airport
        airport = airport.upper()
        async with aiohttp.ClientSession() as session:
            url = f"{BASE_URL}/sessions/{session_id}/airport/{airport}/atis?apikey={IF_API_KEY}"
            async with session.get(url) as resp:
                if resp.status != 200:
                    await interaction.response.send_message(
                        f"❌ Failed to fetch ATIS (HTTP {resp.status}).", ephemeral=True
                    )
                    return

                atis_data = await resp.json()

        # Check API error codes (e.g., No ATIS available)
        error_code = atis_data.get("errorCode")
        result_text = atis_data.get("result")

        if error_code != 0 or not result_text:
            await interaction.response.send_message(
                f"⚠️ No active ATIS available for {airport} on {server}.", ephemeral=True
            )
            return

        # Step 4: Reply with live ATIS
        embed = discord.Embed(
            title=f"ATIS for {airport} — {server}",
            description=f"📡 {result_text}",
            color=discord.Color.green()
        )
        embed.set_footer(text="Data provided by Infinite Flight Live API")
        await interaction.response.send_message(embed=embed)
