import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os

# Use environment variable for security on Railway
IF_API_KEY = os.getenv("IF_API_KEY")
BASE_URL = "https://api.infiniteflight.com/public/v2"

SERVER_MAP = {
    "Casual": "casual",
    "Training": "training",
    "Expert": "expert"
}


def parse_station(station_name: str):
    """
    Splits a stationName like 'EGLL_TWR' into ('EGLL', 'TWR').
    Falls back gracefully if the format is unexpected.
    """
    if "_" in station_name:
        icao, facility = station_name.split("_", 1)
        return icao, facility
    return station_name, "ATC"


class AirportSelect(discord.ui.Select):
    def __init__(self, session_id: str, server_choice: str, airports: list):
        self.session_id = session_id
        self.server_choice = server_choice

        # Discord select menus cap out at 25 options
        options = [
            discord.SelectOption(label=icao, description=f"{count} controller(s) online")
            for icao, count in airports[:25]
        ]

        super().__init__(
            placeholder="Select an airport...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        airport = self.values[0]

        async with aiohttp.ClientSession() as session:
            try:
                atc_url = f"{BASE_URL}/sessions/{self.session_id}/atc?apikey={IF_API_KEY}"
                async with session.get(atc_url) as resp:
                    if resp.status == 401:
                        await interaction.followup.send(
                            "❌ Invalid API key! Please check your Infinite Flight API key.", ephemeral=True
                        )
                        return
                    elif resp.status != 200:
                        await interaction.followup.send(
                            f"⚠️ Failed to fetch ATC data (HTTP {resp.status})", ephemeral=True
                        )
                        return
                    atc_data = await resp.json()
            except Exception as e:
                await interaction.followup.send(f"❌ Error fetching ATC data: {e}", ephemeral=True)
                return

        atc_list = atc_data.get("result", [])
        controllers = [
            c for c in atc_list
            if parse_station(c.get("stationName", ""))[0] == airport
        ]

        if not controllers:
            await interaction.followup.send(
                f"⚠️ No active controllers found at {airport} anymore.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"🎙️ Active ATC — {airport}",
            description=f"Server: **{self.server_choice}**",
            color=discord.Color.blue()
        )

        for c in controllers:
            station = c.get("stationName", "")
            _, facility = parse_station(station)
            username = c.get("username", "Unknown")
            freq = c.get("frequency")

            value_lines = [f"**Controller:** {username}"]
            if freq:
                value_lines.append(f"**Frequency:** {freq}")

            embed.add_field(
                name=f"📍 {facility}",
                value="\n".join(value_lines),
                inline=True
            )

        embed.set_footer(text="AkasaAirVirtual • Infinite Flight Live")
        await interaction.followup.send(embed=embed)


class AirportSelectView(discord.ui.View):
    def __init__(self, session_id: str, server_choice: str, airports: list):
        super().__init__(timeout=120)
        self.add_item(AirportSelect(session_id, server_choice, airports))


class ServerSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Casual", description="Casual Server"),
            discord.SelectOption(label="Training", description="Training Server"),
            discord.SelectOption(label="Expert", description="Expert Server")
        ]
        super().__init__(placeholder="Select a server...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        server_choice = self.values[0]
        server_key = SERVER_MAP[server_choice]

        # Step 1: Find the active session for this server
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{BASE_URL}/sessions?apikey={IF_API_KEY}") as resp:
                    if resp.status == 401:
                        await interaction.followup.send(
                            "❌ Invalid API key! Please check your Infinite Flight API key.", ephemeral=True
                        )
                        return
                    elif resp.status != 200:
                        await interaction.followup.send(
                            f"⚠️ Failed to fetch sessions (HTTP {resp.status})", ephemeral=True
                        )
                        return
                    sessions_data = await resp.json()
            except Exception as e:
                await interaction.followup.send(f"❌ Error fetching sessions: {e}", ephemeral=True)
                return

        sessions = sessions_data.get("result", [])
        session_id = None
        for s in sessions:
            if server_key.lower() in s.get("name", "").lower():
                session_id = s.get("id")
                break

        if not session_id:
            await interaction.followup.send(
                f"⚠️ No active {server_choice} session found.", ephemeral=True
            )
            return

        # Step 2: Fetch all active ATC and build a unique airport list
        async with aiohttp.ClientSession() as session:
            try:
                atc_url = f"{BASE_URL}/sessions/{session_id}/atc?apikey={IF_API_KEY}"
                async with session.get(atc_url) as resp:
                    if resp.status != 200:
                        await interaction.followup.send(
                            f"⚠️ Failed to fetch ATC data (HTTP {resp.status})", ephemeral=True
                        )
                        return
                    atc_data = await resp.json()
            except Exception as e:
                await interaction.followup.send(f"❌ Error fetching ATC data: {e}", ephemeral=True)
                return

        atc_list = atc_data.get("result", [])

        if not atc_list:
            await interaction.followup.send(
                f"⚠️ No active controllers on the {server_choice} server right now.", ephemeral=True
            )
            return

        # Count controllers per airport
        airport_counts = {}
        for c in atc_list:
            icao, _ = parse_station(c.get("stationName", ""))
            if not icao:
                continue
            airport_counts[icao] = airport_counts.get(icao, 0) + 1

        airports = sorted(airport_counts.items(), key=lambda x: x[0])

        if not airports:
            await interaction.followup.send(
                f"⚠️ No active controllers on the {server_choice} server right now.", ephemeral=True
            )
            return

        note = ""
        if len(airports) > 25:
            note = f"\n(Showing first 25 of {len(airports)} airports — try narrowing down by region)"

        await interaction.followup.send(
            content=f"✈️ Active ATC airports on **{server_choice}**:{note}",
            view=AirportSelectView(session_id, server_choice, airports),
            ephemeral=True
        )


class ServerSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(ServerSelect())


class ATC(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="atc", description="Show active ATC airports and controller info on Infinite Flight")
    async def atc(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Select a server to view active ATC:",
            view=ServerSelectView(),
            ephemeral=True
        )


# Mandatory setup function
async def setup(bot):
    await bot.add_cog(ATC(bot))
