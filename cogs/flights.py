import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os

IF_API_KEY = os.getenv("IF_API_KEY")
BASE_URL = "https://api.infiniteflight.com/public/v2"

SERVER_MAP = {
    "Casual": "casual",
    "Training": "training",
    "Expert": "expert"
}

class Flights(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="activeflights", description="List all active Akasa Air flights (callsign ending with QP)")
    @app_commands.describe(server="Select server")
    @app_commands.choices(server=[
        app_commands.Choice(name="Casual", value="Casual"),
        app_commands.Choice(name="Training", value="Training"),
        app_commands.Choice(name="Expert", value="Expert")
    ])
    async def activeflights(self, interaction: discord.Interaction, server: app_commands.Choice[str]):
        server_key = SERVER_MAP[server.value]

        # Step 1: Fetch sessions
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/sessions?apikey={IF_API_KEY}") as resp:
                if resp.status != 200:
                    await interaction.response.send_message(f"❌ Failed to fetch sessions (HTTP {resp.status})", ephemeral=True)
                    return
                sessions_data = await resp.json()

        sessions = sessions_data.get("result", [])
        session_id = None
        for s in sessions:
            if server_key.lower() in s.get("name", "").lower():
                session_id = s.get("id")
                break

        if not session_id:
            await interaction.response.send_message(f"⚠️ No active {server.value} session found.", ephemeral=True)
            return

        # Step 2: Fetch all flights
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/sessions/{session_id}/flights?apikey={IF_API_KEY}") as resp:
                if resp.status != 200:
                    await interaction.response.send_message(f"❌ Failed to fetch flights (HTTP {resp.status})", ephemeral=True)
                    return
                flights_data = await resp.json()

        flights = flights_data.get("result", [])

        # Step 3: Filter for QP callsigns
        qp_flights = [f for f in flights if f.get("callsign", "").endswith("QP")]

        if not qp_flights:
            await interaction.response.send_message("⚠️ No active Akasa Air QP flights currently.", ephemeral=True)
            return

        # Step 4: Build embed
        embed = discord.Embed(
            title=f"🛫 Active Akasa Air QP Flights — {server.value}",
            color=discord.Color.orange()
        )

        for f in qp_flights:
            callsign = f.get("callsign", "N/A")
            aircraft = f.get("aircraft", "N/A")
            departure = f.get("departure", "N/A")
            arrival = f.get("arrival", "N/A")
            altitude = f.get("altitude", 0)
            speed = f.get("speed", 0)
            embed.add_field(
                name=callsign,
                value=f"✈️ {aircraft}\nFrom {departure} → {arrival}\n🛫 Altitude: {altitude} ft | 🏎️ Speed: {speed} kts",
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="flightinfo", description="Get live info for a specific Akasa Air QP flight")
    @app_commands.describe(callsign="Flight callsign (ending with QP)")
    async def flightinfo(self, interaction: discord.Interaction, callsign: str):
        callsign = callsign.upper()
        if not callsign.endswith("QP"):
            await interaction.response.send_message("❌ Only Akasa Air QP flights are supported.", ephemeral=True)
            return

        # Step 1: Fetch sessions
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/sessions?apikey={IF_API_KEY}") as resp:
                if resp.status != 200:
                    await interaction.response.send_message(f"❌ Failed to fetch sessions (HTTP {resp.status})", ephemeral=True)
                    return
                sessions_data = await resp.json()

        sessions = sessions_data.get("result", [])
        session_id = sessions[0].get("id") if sessions else None
        if not session_id:
            await interaction.response.send_message("⚠️ No active session found.", ephemeral=True)
            return

        # Step 2: Fetch all flights
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/sessions/{session_id}/flights?apikey={IF_API_KEY}") as resp:
                if resp.status != 200:
                    await interaction.response.send_message(f"❌ Failed to fetch flights (HTTP {resp.status})", ephemeral=True)
                    return
                flights_data = await resp.json()

        flights = flights_data.get("result", [])
        flight = next((f for f in flights if f.get("callsign", "").upper() == callsign), None)

        if not flight:
            await interaction.response.send_message(f"⚠️ Flight {callsign} not found.", ephemeral=True)
            return

        # Step 3: Build embed
        embed = discord.Embed(
            title=f"✈️ Flight Info — {callsign}",
            color=discord.Color.orange()
        )
        embed.add_field(name="Aircraft", value=flight.get("aircraft", "N/A"), inline=True)
        embed.add_field(name="Departure", value=flight.get("departure", "N/A"), inline=True)
        embed.add_field(name="Arrival", value=flight.get("arrival", "N/A"), inline=True)
        embed.add_field(name="Altitude", value=f"{flight.get('altitude', 0)} ft", inline=True)
        embed.add_field(name="Speed", value=f"{flight.get('speed', 0)} kts", inline=True)
        embed.add_field(name="Server", value=flight.get("server", "N/A"), inline=True)

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Flights(bot))
