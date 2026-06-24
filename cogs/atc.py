import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
from datetime import datetime, timezone

# Use environment variable for security on Railway
IF_API_KEY = os.getenv("IF_API_KEY")
BASE_URL = "https://api.infiniteflight.com/public/v2"

SERVER_MAP = {
    "Casual": "casual",
    "Training": "training",
    "Expert": "expert"
}


FACILITY_TYPES = {
    0: "Ground",
    1: "Tower",
    2: "Unicom",
    3: "Clearance",
    4: "Approach",
    5: "Departure",
    6: "Center",
    7: "ATIS"
}


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
            if c.get("airportName") == airport
        ]

        if not controllers:
            await interaction.followup.send(
                f"⚠️ No active controllers found at {airport} anymore.", ephemeral=True
            )
            return

        # Rebuild the full airport list (for the dropdown to remain usable after this)
        airport_counts = {}
        for c in atc_list:
            icao = c.get("airportName")
            if icao:
                airport_counts[icao] = airport_counts.get(icao, 0) + 1
        airports = sorted(airport_counts.items(), key=lambda x: x[0])

        embed = discord.Embed(
            title=f"🎙️ Live Infinite Flight {self.server_choice} Server ATC",
            description=f"**Airport:** {airport}",
            color=discord.Color.blue()
        )

        map_lat, map_lng = None, None

        # Build table rows
        col1, col2, col3 = "Facility", "Controller", "Active For"
        w1, w2, w3 = len(col1), len(col2), len(col3)

        rows = []
        for c in controllers:
            facility = FACILITY_TYPES.get(c.get("type"), f"Type {c.get('type')}")
            username = c.get("username", "Unknown")
            active_str = "N/A"

            start_time_raw = c.get("startTime")
            if start_time_raw:
                try:
                    start_dt = datetime.fromisoformat(start_time_raw.replace("Z", "+00:00"))
                    elapsed = datetime.now(timezone.utc) - start_dt
                    hours, remainder = divmod(int(elapsed.total_seconds()), 3600)
                    mins = remainder // 60
                    active_str = f"{hours}h {mins:02d}m"
                except Exception:
                    pass

            if map_lat is None and c.get("latitude") is not None:
                map_lat = c.get("latitude")
                map_lng = c.get("longitude")

            rows.append((facility, username, active_str))
            w1 = max(w1, len(facility))
            w2 = max(w2, len(username))
            w3 = max(w3, len(active_str))

        # Assemble the table string
        header = f"{col1:<{w1}}  {col2:<{w2}}  {col3:<{w3}}"
        divider = f"{'─' * w1}  {'─' * w2}  {'─' * w3}"
        table_lines = [header, divider]
        for facility, username, active_str in rows:
            table_lines.append(f"{facility:<{w1}}  {username:<{w2}}  {active_str:<{w3}}")

        embed.add_field(
            name="\u200b",
            value=f"```\n{chr(10).join(table_lines)}\n```",
            inline=False
        )

        embed.set_footer(text=f"Showing {len(controllers)}/{len(controllers)} • AkasaAirVirtual • Infinite Flight Live")

        view = discord.ui.View(timeout=120)
        if map_lat is not None and map_lng is not None:
            view.add_item(
                discord.ui.Button(
                    label="View On Static Map",
                    style=discord.ButtonStyle.link,
                    url=f"https://www.google.com/maps?q={map_lat},{map_lng}"
                )
            )
        view.add_item(AirportSelect(self.session_id, self.server_choice, airports))

        await interaction.followup.send(embed=embed, view=view)


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
            icao = c.get("airportName")
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
