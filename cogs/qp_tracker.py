import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import os

IF_API_KEY = os.getenv("IF_API_KEY")
BASE_URL = "https://api.infiniteflight.com/public/v2"

class FlightTracker(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.radar_message = None
        self.update_radar.start()

    async def get_session_id(self):

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/sessions?apikey={IF_API_KEY}") as resp:
                data = await resp.json()

        for s in data["result"]:
            if "Expert" in s["name"]:
                return s["id"]

        return data["result"][0]["id"]

    async def get_flights(self):

        session_id = await self.get_session_id()

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/sessions/{session_id}/flights?apikey={IF_API_KEY}") as resp:
                data = await resp.json()

        return data["result"]

    @app_commands.command(name="flighttracker", description="Show live Akasa Air flights")
    async def flighttracker(self, interaction: discord.Interaction):

        await interaction.response.defer()

        flights = await self.get_flights()

        qp_flights = [
            f for f in flights
            if f["callsign"].endswith("QP")
        ]

        embed = discord.Embed(
            title="🛫 Akasa Air Live Flight Tracker",
            color=discord.Color.orange()
        )

        if not qp_flights:
            embed.description = "No QP flights currently active."
        else:

            for f in qp_flights[:15]:

                embed.add_field(
                    name=f["callsign"],
                    value=(
                        f"Route: {f['departureAirportIcao']} → {f['arrivalAirportIcao']}\n"
                        f"Aircraft: {f['aircraftId']}\n"
                        f"Altitude: {round(f['altitude'])} ft\n"
                        f"Speed: {round(f['speed'])} kts"
                    ),
                    inline=False
                )

        msg = await interaction.followup.send(embed=embed)
        self.radar_message = msg

    @tasks.loop(seconds=30)
    async def update_radar(self):

        if not self.radar_message:
            return

        flights = await self.get_flights()

        qp_flights = [
            f for f in flights
            if f["callsign"].endswith("QP")
        ]

        embed = discord.Embed(
            title="🛫 Akasa Air Live Flight Tracker",
            color=discord.Color.orange()
        )

        if not qp_flights:
            embed.description = "No QP flights currently active."
        else:

            for f in qp_flights[:15]:

                embed.add_field(
                    name=f["callsign"],
                    value=(
                        f"Route: {f['departureAirportIcao']} → {f['arrivalAirportIcao']}\n"
                        f"Aircraft: {f['aircraftId']}\n"
                        f"Altitude: {round(f['altitude'])} ft\n"
                        f"Speed: {round(f['speed'])} kts"
                    ),
                    inline=False
                )

        try:
            await self.radar_message.edit(embed=embed)
        except:
            self.radar_message = None


async def setup(bot):
    await bot.add_cog(FlightTracker(bot))
