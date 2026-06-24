import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
from datetime import datetime, timezone

IF_API_KEY = os.getenv("IF_API_KEY")
BASE_URL = "https://api.infiniteflight.com/public/v2"

SERVER_MAP = {
    "Casual": "casual",
    "Training": "training",
    "Expert": "expert"
}

# Confirmed from official docs:
# Ground=0, Tower=1, Unicom=2, Clearance=3, Approach=4,
# Departure=5, Center=6, ATIS=7, Aircraft=8, Recorded=9, Unknown=10, Unused=11
FACILITY_TYPES = {
    0: "Ground",
    1: "Tower",
    2: "Unicom",
    3: "Clearance",
    4: "Approach",
    5: "Departure",
    6: "Center",
    7: "ATIS",
    8: "Aircraft",
    9: "Recorded",
    10: "Unknown",
    11: "Unused"
}


async def fetch_session_id(server_key: str) -> str | None:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/sessions?apikey={IF_API_KEY}") as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    for s in data.get("result", []):
        if server_key.lower() in s.get("name", "").lower():
            return s.get("id")
    return None


async def fetch_world(session_id: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{BASE_URL}/sessions/{session_id}/world?apikey={IF_API_KEY}"
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    return data.get("result", [])


def build_airport_embed(airport: dict, server_choice: str) -> discord.Embed:
    icao = airport.get("airportIcao", "N/A")
    name = airport.get("airportName") or icao
    inbound = airport.get("inboundFlightsCount", 0)
    outbound = airport.get("outboundFlightsCount", 0)
    facilities = airport.get("atcFacilities", [])

    embed = discord.Embed(
        title=f"🌍 {name} ({icao})",
        description=f"**Server:** {server_choice}",
        color=discord.Color.orange()
    )

    embed.add_field(
        name="✈️ Traffic",
        value=(
            f"🛬 **Inbound:** {inbound}\n"
            f"🛫 **Outbound:** {outbound}\n"
            f"📊 **Total:** {inbound + outbound}"
        ),
        inline=True
    )

    if facilities:
        # Build a compact table of active ATC
        col1, col2, col3 = "Facility", "Controller", "Active"
        w1 = max(len(col1), max((len(FACILITY_TYPES.get(f.get("type", 10), "Unknown")) for f in facilities), default=0))
        w2 = max(len(col2), max((len(f.get("username") or "N/A") for f in facilities), default=0))
        w3 = max(len(col3), 6)

        header = f"{col1:<{w1}}  {col2:<{w2}}  {col3}"
        divider = f"{'─' * w1}  {'─' * w2}  {'─' * w3}"
        rows = [header, divider]

        for f in facilities:
            facility = FACILITY_TYPES.get(f.get("type", 10), "Unknown")
            username = f.get("username") or "N/A"
            active_str = "N/A"
            start_raw = f.get("startTime")
            if start_raw:
                try:
                    start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
                    elapsed = datetime.now(timezone.utc) - start_dt
                    h, rem = divmod(int(elapsed.total_seconds()), 3600)
                    m = rem // 60
                    active_str = f"{h}h {m:02d}m"
                except Exception:
                    pass
            rows.append(f"{facility:<{w1}}  {username:<{w2}}  {active_str}")

        embed.add_field(
            name="🎙️ Active ATC",
            value=f"```\n{chr(10).join(rows)}\n```",
            inline=False
        )
    else:
        embed.add_field(
            name="🎙️ Active ATC",
            value="No active controllers.",
            inline=False
        )

    embed.set_footer(text=f"AkasaAirVirtual • Infinite Flight Live • {server_choice} Server")
    return embed


class AirportSelectDropdown(discord.ui.Select):
    def __init__(self, world_data: list, server_choice: str):
        self.world_data = world_data
        self.server_choice = server_choice

        # Sort by total traffic descending, cap at 25 (Discord limit)
        sorted_airports = sorted(
            world_data,
            key=lambda a: a.get("inboundFlightsCount", 0) + a.get("outboundFlightsCount", 0),
            reverse=True
        )[:25]

        options = []
        for a in sorted_airports:
            icao = a.get("airportIcao", "N/A")
            name = (a.get("airportName") or icao)[:50]
            inbound = a.get("inboundFlightsCount", 0)
            outbound = a.get("outboundFlightsCount", 0)
            atc_count = len(a.get("atcFacilities", []))
            options.append(
                discord.SelectOption(
                    label=f"{icao} — {name}"[:100],
                    description=f"🛬 {inbound} in  🛫 {outbound} out  🎙️ {atc_count} ATC",
                    value=icao
                )
            )

        super().__init__(
            placeholder="🌍 Select an airport to view details...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        selected_icao = self.values[0]
        airport = next(
            (a for a in self.world_data if a.get("airportIcao") == selected_icao),
            None
        )
        if not airport:
            return await interaction.response.send_message(
                "⚠️ Airport data not found.", ephemeral=True
            )

        embed = build_airport_embed(airport, self.server_choice)
        view = discord.ui.View(timeout=120)
        view.add_item(AirportSelectDropdown(self.world_data, self.server_choice))
        await interaction.response.edit_message(embed=embed, view=view)


class ServerSelectDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Expert", description="Expert Server", emoji="🟠"),
            discord.SelectOption(label="Training", description="Training Server", emoji="🔵"),
            discord.SelectOption(label="Casual", description="Casual Server", emoji="🟢")
        ]
        super().__init__(placeholder="✈️ Select a server...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        server_choice = self.values[0]
        server_key = SERVER_MAP[server_choice]

        session_id = await fetch_session_id(server_key)
        if not session_id:
            return await interaction.followup.send(
                f"⚠️ No active {server_choice} session found.", ephemeral=True
            )

        world_data = await fetch_world(session_id)
        if world_data is None:
            return await interaction.followup.send(
                "⚠️ Failed to fetch world status.", ephemeral=True
            )

        if not world_data:
            return await interaction.followup.send(
                f"⚠️ No active airports found on the {server_choice} server.", ephemeral=True
            )

        # Summary stats
        total_airports = len(world_data)
        total_inbound = sum(a.get("inboundFlightsCount", 0) for a in world_data)
        total_outbound = sum(a.get("outboundFlightsCount", 0) for a in world_data)
        total_atc = sum(len(a.get("atcFacilities", [])) for a in world_data)

        embed = discord.Embed(
            title=f"🌍 Infinite Flight {server_choice} Server — World Status",
            description=(
                f"**Active Airports:** {total_airports}\n"
                f"🛬 **Total Inbound:** {total_inbound}\n"
                f"🛫 **Total Outbound:** {total_outbound}\n"
                f"🎙️ **Active Controllers:** {total_atc}\n\n"
                f"Select an airport below to view its traffic and ATC details."
            ),
            color=discord.Color.orange()
        )

        # Top 5 busiest airports preview
        sorted_airports = sorted(
            world_data,
            key=lambda a: a.get("inboundFlightsCount", 0) + a.get("outboundFlightsCount", 0),
            reverse=True
        )[:5]

        top_lines = []
        for a in sorted_airports:
            icao = a.get("airportIcao", "N/A")
            total = a.get("inboundFlightsCount", 0) + a.get("outboundFlightsCount", 0)
            atc = len(a.get("atcFacilities", []))
            top_lines.append(f"**{icao}** — {total} flights, {atc} ATC")

        embed.add_field(
            name="🏆 Top 5 Busiest Airports",
            value="\n".join(top_lines) if top_lines else "None",
            inline=False
        )

        embed.set_footer(text=f"AkasaAirVirtual • Infinite Flight Live • Showing top 25 airports")

        view = discord.ui.View(timeout=180)
        view.add_item(AirportSelectDropdown(world_data, server_choice))

        await interaction.followup.send(embed=embed, view=view)


class WorldStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="worldstatus",
        description="View live Infinite Flight world traffic and ATC status"
    )
    async def worldstatus(self, interaction: discord.Interaction):
        view = discord.ui.View(timeout=120)
        view.add_item(ServerSelectDropdown())

        await interaction.response.send_message(
            "🌍 Select a server to view world status:",
            view=view,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(WorldStatus(bot))
