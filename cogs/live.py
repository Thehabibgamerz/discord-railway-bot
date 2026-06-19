import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
import math

# Use environment variable for security on Railway
IF_API_KEY = os.getenv("IF_API_KEY")
BASE_URL = "https://api.infiniteflight.com/public/v2"


def haversine_nm(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points in nautical miles."""
    R_nm = 3440.065
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R_nm * math.asin(math.sqrt(a))


async def fetch_json(session, url):
    async with session.get(url) as resp:
        if resp.status != 200:
            return None, resp.status
        return await resp.json(), resp.status


class LiveFlightView(discord.ui.View):
    """Lets the user page through multiple matching flights."""

    def __init__(self, session_id: str, matches: list, index: int = 0):
        super().__init__(timeout=180)
        self.session_id = session_id
        self.matches = matches
        self.index = index
        self._update_buttons()

    def _update_buttons(self):
        self.previous_button.disabled = self.index <= 0
        self.next_button.disabled = self.index >= len(self.matches) - 1

    async def build_embed(self):
        flight = self.matches[self.index]
        return await build_flight_embed(self.session_id, flight, self.index, len(self.matches))

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index -= 1
        self._update_buttons()
        embed = await self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index += 1
        self._update_buttons()
        embed = await self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)


async def build_flight_embed(session_id: str, flight: dict, index: int, total: int):
    username = flight.get("username", "Unknown")
    callsign = flight.get("callsign") or flight.get("virtualOrganization") or "N/A"
    flight_id = flight.get("flightId") or flight.get("id")

    altitude = flight.get("altitude")
    speed = flight.get("speed") or flight.get("groundSpeed")
    lat = flight.get("latitude")
    lon = flight.get("longitude")
    aircraft_id = flight.get("aircraftId")
    livery_id = flight.get("liveryId")

    aircraft_name = "Unknown"
    livery_name = "Unknown"
    departure = "N/A"
    arrival = "N/A"
    sid = "N/A"
    star = "N/A"
    approach = "N/A"
    short_route = "N/A"
    progress_pct = None
    eta_text = "N/A"

    debug_text = None

    async with aiohttp.ClientSession() as session:

        # Aircraft / livery lookup
        try:
            aircraft_data, status = await fetch_json(
                session, f"{BASE_URL}/aircraft/liveries?apikey={IF_API_KEY}"
            )
            if aircraft_data:
                liveries = aircraft_data.get("result", [])
                for lv in liveries:
                    if lv.get("id") == livery_id:
                        livery_name = lv.get("liveryName", "Unknown")
                        aircraft_name = lv.get("aircraftName", "Unknown")
                        break
        except Exception:
            pass

        # Flight plan lookup — confirmed endpoint from official docs
        if flight_id:
            fp_url = f"{BASE_URL}/sessions/{session_id}/flights/{flight_id}/flightplan?apikey={IF_API_KEY}"

            try:
                fp_data, status = await fetch_json(session, fp_url)

                if fp_data is None:
                    debug_text = f"flightplan endpoint → HTTP {status} | flightId used: `{flight_id}`"
                else:
                    fp_result = fp_data.get("result", {})
                    items = fp_result.get("flightPlanItems", []) or fp_result.get("waypoints", [])

                    if not items:
                        import json
                        debug_text = (
                            "Flightplan endpoint responded but no flightPlanItems/waypoints found. Raw response:\n"
                            f"```json\n{json.dumps(fp_data, indent=2)[:1200]}\n```"
                        )

                    waypoint_ids = [i.get("identifier") for i in items if i.get("identifier")]

                    if waypoint_ids:
                        departure = waypoint_ids[0]
                        arrival = waypoint_ids[-1]
                        short_route = " ".join(waypoint_ids)

                    # If the API tags item types (SID/STAR/APPROACH), pull those out
                    for i in items:
                        item_type = (i.get("type") or "").upper()
                        if item_type == "SID":
                            sid = i.get("identifier", sid)
                        elif item_type == "STAR":
                            star = i.get("identifier", star)
                        elif item_type == "APPROACH":
                            approach = i.get("identifier", approach)

                    # Progress + ETA based on remaining distance to destination
                    if waypoint_ids and lat is not None and lon is not None:
                        dest_item = items[-1]
                        dest_lat = dest_item.get("latitude")
                        dest_lon = dest_item.get("longitude")
                        origin_item = items[0]
                        origin_lat = origin_item.get("latitude")
                        origin_lon = origin_item.get("longitude")

                        if None not in (dest_lat, dest_lon, origin_lat, origin_lon):
                            total_dist = haversine_nm(origin_lat, origin_lon, dest_lat, dest_lon)
                            remaining_dist = haversine_nm(lat, lon, dest_lat, dest_lon)

                            if total_dist > 0:
                                progress_pct = max(0, min(100, round((1 - remaining_dist / total_dist) * 100)))

                            if speed and speed > 0:
                                eta_hours = remaining_dist / speed
                                eta_minutes = int(eta_hours * 60)
                                hrs, mins = divmod(eta_minutes, 60)
                                eta_text = f"{hrs}h {mins}m"
            except Exception as e:
                debug_text = f"Exception: {e}"

    embed = discord.Embed(
        title=f"{username} | {callsign}",
        description=f"**{departure} → {arrival}**",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="✈️ Aircraft",
        value=f"**Type:** {aircraft_name}\n**Livery:** {livery_name}",
        inline=False
    )

    embed.add_field(
        name="📊 Stats",
        value=(
            f"**Altitude:** {altitude:.0f} Feet\n" if isinstance(altitude, (int, float)) else "**Altitude:** N/A\n"
        ) + (
            f"**Speed (Ground Speed):** {speed:.0f} Knots\n" if isinstance(speed, (int, float)) else "**Speed:** N/A\n"
        ) + (
            f"**Progress:** {progress_pct}%\n" if progress_pct is not None else "**Progress:** N/A\n"
        ) + f"**ETA:** {eta_text}",
        inline=False
    )

    embed.add_field(
        name="🗺️ Route Info",
        value=(
            f"**Departure Airport:** {departure}\n"
            f"**SID:** {sid}\n"
            f"**STAR:** {star}\n"
            f"**APPROACH:** {approach}\n"
            f"**Arrival Airport:** {arrival}"
        ),
        inline=False
    )

    embed.add_field(
        name="Short Route: (Without waypoints of STAR/SID/APP)",
        value=f"```{short_route}```",
        inline=False
    )

    if debug_text:
        embed.add_field(
            name="🛠️ Debug (flight plan lookup)",
            value=debug_text[:1000],
            inline=False
        )

    embed.set_footer(text=f"Showing {index + 1}/{total} • AkasaAirVirtual • Infinite Flight Live")

    return embed


class Live(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="live", description="Track a live flight on the Expert server")
    @app_commands.describe(query="Callsign or Infinite Flight username")
    async def live(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)

        # Step 1: Find the active Expert server session
        async with aiohttp.ClientSession() as session:
            sessions_data, status = await fetch_json(session, f"{BASE_URL}/sessions?apikey={IF_API_KEY}")

            if sessions_data is None:
                if status == 401:
                    await interaction.followup.send("❌ Invalid API key!", ephemeral=True)
                else:
                    await interaction.followup.send(f"⚠️ Failed to fetch sessions (HTTP {status})", ephemeral=True)
                return

        sessions = sessions_data.get("result", [])
        session_id = None
        for s in sessions:
            if "expert" in s.get("name", "").lower():
                session_id = s.get("id")
                break

        if not session_id:
            await interaction.followup.send("⚠️ No active Expert server session found.", ephemeral=True)
            return

        # Step 2: Fetch all flights and search by callsign/username
        async with aiohttp.ClientSession() as session:
            flights_data, status = await fetch_json(
                session, f"{BASE_URL}/sessions/{session_id}/flights?apikey={IF_API_KEY}"
            )

            if flights_data is None:
                await interaction.followup.send(f"⚠️ Failed to fetch flights (HTTP {status})", ephemeral=True)
                return

        flights = flights_data.get("result", [])
        query_lower = query.lower()

        matches = [
            f for f in flights
            if query_lower in (f.get("username") or "").lower()
            or query_lower in (f.get("callsign") or "").lower()
        ]

        if not matches:
            await interaction.followup.send(
                f"⚠️ No active flights found matching `{query}` on the Expert server.", ephemeral=True
            )
            return

        embed = await build_flight_embed(session_id, matches[0], 0, len(matches))
        view = LiveFlightView(session_id, matches, 0) if len(matches) > 1 else None

        if view:
            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send(embed=embed)


# Mandatory setup function
async def setup(bot):
    await bot.add_cog(Live(bot))
