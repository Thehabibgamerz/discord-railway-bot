
# ================================================================
# ✈️ AKASA AIR VIRTUAL — INFINITE FLIGHT LIVE TRACKER
# File: cogs/live.py
# Python 3.10+ | discord.py 2.x | aiohttp
# ================================================================

import os
import math
import logging
import asyncio
from time import monotonic
from urllib.parse import quote

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

BASE_URL = "https://api.infiniteflight.com/public/v2"
IF_API_KEY = os.getenv("IF_API_KEY")

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)
METADATA_CACHE_SECONDS = 1800
SESSION_CACHE_SECONDS = 30

# API data is cached temporarily in memory only.
# Do not persist Live API flight data in a database.

# ================================================================
# HELPERS
# ================================================================

def number(value):
    """Return a number or None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return value
    return None


def display_number(value, decimals=0):
    value = number(value)
    return f"{value:,.{decimals}f}" if value is not None else "N/A"


def get_position(flight):
    """Support both common top-level and nested location formats."""
    location = flight.get("location") or {}

    lat = flight.get("latitude", location.get("latitude"))
    lon = flight.get("longitude", location.get("longitude"))

    lat, lon = number(lat), number(lon)

    if lat is None or lon is None:
        return None, None

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, None

    if lat == 0 and lon == 0:
        return None, None

    return lat, lon


def haversine_nm(lat1, lon1, lat2, lon2):
    """Great-circle distance in nautical miles."""
    earth_radius_nm = 3440.065

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1)
        * math.cos(p2)
        * math.sin(dlambda / 2) ** 2
    )
    a = max(0.0, min(1.0, a))

    return 2 * earth_radius_nm * math.asin(math.sqrt(a))


def get_flight_id(flight):
    return flight.get("flightId") or flight.get("id")


def get_flight_label(flight):
    return (
        flight.get("callsign")
        or flight.get("username")
        or "Unknown flight"
    )


def build_map_url(points, current_position=None):
    """Build a lightweight static map URL if route coordinates exist."""
    coords = []

    for item in points:
        loc = item.get("location") or {}
        lat = number(loc.get("latitude"))
        lon = number(loc.get("longitude"))

        if lat is not None and lon is not None:
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                if (lat, lon) != (0, 0):
                    coords.append((lat, lon))

    if not coords:
        return None

    # Keep the URL within reasonable length limits.
    if len(coords) > 35:
        step = max(1, len(coords) // 35)
        coords = coords[::step]

    path = "|".join(f"{lat},{lon}" for lat, lon in coords)

    markers = (
        f"{coords[0][0]},{coords[0][1]},lightblue1|"
        f"{coords[-1][0]},{coords[-1][1]},lightblue2"
    )

    if current_position:
        lat, lon = current_position
        markers += f"|{lat},{lon},red-pushpin"

    url = (
        "https://staticmap.openstreetmap.de/staticmap.php"
        f"?size=600x400&maptype=mapnik"
        f"&path=color:0x0055ffaa|weight:3|{quote(path, safe=',|:.')}"
        f"&markers={quote(markers, safe=',|')}"
    )

    return url


def extract_plan_items(plan_data):
    if not isinstance(plan_data, dict):
        return []

    result = plan_data.get("result") or {}

    if isinstance(result, list):
        return result

    if isinstance(result, dict):
        items = result.get("flightPlanItems") or result.get("items") or []
        return items if isinstance(items, list) else []

    return []


def find_procedures(items):
    sid = "N/A"
    star = "N/A"
    approach = "N/A"

    # These type mappings follow the convention used by the supplied
    # code. Only display a procedure when a procedure item is present.
    procedure_types = {
        0: "sid",
        1: "star",
        2: "approach",
    }

    for item in items:
        if not item.get("children"):
            continue

        label = procedure_types.get(item.get("type"))
        name = item.get("name") or item.get("identifier") or "N/A"

        if label == "sid":
            sid = name
        elif label == "star":
            star = name
        elif label == "approach":
            approach = name

    return sid, star, approach


# ================================================================
# TRACKER COG
# ================================================================

class Live(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.http: aiohttp.ClientSession | None = None

        self._session_cache = None
        self._session_cache_time = 0.0

        self._metadata_cache = None
        self._metadata_cache_time = 0.0

        self._metadata_lock = asyncio.Lock()

    async def cog_load(self):
        if not IF_API_KEY:
            logger.warning(
                "IF_API_KEY is not configured. /live will not work until "
                "the Railway environment variable is added."
            )

        self.http = aiohttp.ClientSession(timeout=REQUEST_TIMEOUT)

    async def cog_unload(self):
        if self.http and not self.http.closed:
            await self.http.close()

    async def api_get(self, path, params=None):
        """Return parsed API JSON and HTTP status."""
        if not IF_API_KEY:
            return None, 0, "IF_API_KEY is not configured."

        if self.http is None or self.http.closed:
            return None, 0, "HTTP session is not available."

        query_params = {"apikey": IF_API_KEY}
        if params:
            query_params.update(params)

        url = f"{BASE_URL}/{path.lstrip('/')}"

        try:
            async with self.http.get(url, params=query_params) as response:
                status = response.status

                if status != 200:
                    # Never log or return the URL; it contains the API key.
                    body = await response.text()
                    logger.warning(
                        "Infinite Flight API returned HTTP %s for %s: %s",
                        status,
                        path,
                        body[:250],
                    )
                    return None, status, None

                data = await response.json(content_type=None)

                if not isinstance(data, dict):
                    return None, status, "Unexpected API response format."

                error_code = data.get("errorCode")
                if error_code not in (None, 0):
                    logger.warning(
                        "Infinite Flight API errorCode=%s for %s",
                        error_code,
                        path,
                    )
                    return None, status, f"API error code {error_code}"

                return data, status, None

        except asyncio.TimeoutError:
            return None, 0, "The Infinite Flight API timed out."
        except aiohttp.ClientError:
            logger.exception("Network error calling Infinite Flight API.")
            return None, 0, "Network error while contacting Infinite Flight."
        except ValueError:
            return None, 0, "Infinite Flight returned invalid JSON."

    async def get_expert_session(self):
        now = monotonic()

        if (
            self._session_cache
            and now - self._session_cache_time < SESSION_CACHE_SECONDS
        ):
            return self._session_cache

        data, status, error = await self.api_get("sessions")

        if not data:
            return None

        sessions = data.get("result") or []

        # Prefer the official worldType enum:
        # Solo=0, Casual=1, Training=2, Expert=3, Private=4.
        expert = next(
            (
                session for session in sessions
                if session.get("worldType") == 3
            ),
            None,
        )

        # Fallback for older/inconsistent responses.
        if expert is None:
            expert = next(
                (
                    session for session in sessions
                    if "expert" in (session.get("name") or "").lower()
                ),
                None,
            )

        if expert:
            self._session_cache = expert
            self._session_cache_time = now

        return expert

    async def get_metadata(self):
        now = monotonic()

        if (
            self._metadata_cache is not None
            and now - self._metadata_cache_time < METADATA_CACHE_SECONDS
        ):
            return self._metadata_cache

        async with self._metadata_lock:
            now = monotonic()

            if (
                self._metadata_cache is not None
                and now - self._metadata_cache_time < METADATA_CACHE_SECONDS
            ):
                return self._metadata_cache

            data, _, _ = await self.api_get("aircraft/liveries")

            if not data:
                return self._metadata_cache or {}

            metadata = {}

            for item in data.get("result") or []:
                livery_id = item.get("id")
                if livery_id:
                    metadata[livery_id] = {
                        "aircraft": item.get("aircraftName") or "Unknown",
                        "livery": item.get("liveryName") or "Unknown",
                    }

            self._metadata_cache = metadata
            self._metadata_cache_time = now

            return metadata

    async def get_flights(self, session_id):
        data, status, error = await self.api_get(
            f"sessions/{session_id}/flights"
        )

        if not data:
            return None, status, error

        flights = data.get("result") or []
        return flights, status, None

    async def get_flight_plan(self, session_id, flight_id):
        if not flight_id:
            return [], "Flight ID unavailable."

        data, status, error = await self.api_get(
            f"sessions/{session_id}/flights/{flight_id}/flightplan"
        )

        if not data:
            if status == 404:
                return [], "No flight plan available for this flight."
            return [], error or "Flight plan unavailable."

        return extract_plan_items(data), None

    # ============================================================
    # FLIGHT EMBED
    # ============================================================

    async def build_flight_embed(
        self,
        session_id: str,
        flight: dict,
        index: int,
        total: int,
    ):
        username = flight.get("username") or "Unknown pilot"
        callsign = (
            flight.get("callsign")
            or flight.get("virtualOrganization")
            or "N/A"
        )
        flight_id = get_flight_id(flight)

        altitude = number(flight.get("altitude"))
        speed = number(
            flight.get("speed")
            if flight.get("speed") is not None
            else flight.get("groundSpeed")
        )
        lat, lon = get_position(flight)

        livery_id = flight.get("liveryId")
        metadata = await self.get_metadata()
        aircraft_info = metadata.get(livery_id, {})

        aircraft_name = aircraft_info.get("aircraft", "Unknown")
        livery_name = aircraft_info.get("livery", "Unknown")

        items, plan_error = await self.get_flight_plan(
            session_id,
            flight_id,
        )

        waypoint_names = [
            item.get("name")
            for item in items
            if item.get("name")
        ]

        departure = waypoint_names[0] if waypoint_names else "N/A"
        arrival = waypoint_names[-1] if waypoint_names else "N/A"

        sid, star, approach = find_procedures(items)

        route_text = (
            " → ".join(waypoint_names[:35])
            if waypoint_names
            else "No filed flight plan available"
        )

        # ETA is an estimate based on straight-line distance and the
        # reported speed. It is not an official simulator ETA.
        progress_text = "N/A"
        eta_text = "N/A"
        remaining_text = "N/A"

        if items and lat is not None and lon is not None:
            destination = items[-1].get("location") or {}
            origin = items[0].get("location") or {}

            dest_lat = number(destination.get("latitude"))
            dest_lon = number(destination.get("longitude"))
            orig_lat = number(origin.get("latitude"))
            orig_lon = number(origin.get("longitude"))

            if None not in (dest_lat, dest_lon, orig_lat, orig_lon):
                total_distance = haversine_nm(
                    orig_lat, orig_lon, dest_lat, dest_lon
                )
                remaining_distance = haversine_nm(
                    lat, lon, dest_lat, dest_lon
                )

                remaining_text = f"{remaining_distance:,.1f} NM"

                if total_distance > 0:
                    progress = max(
                        0,
                        min(
                            100,
                            round(
                                (1 - remaining_distance / total_distance) * 100
                            ),
                        ),
                    )
                    progress_text = f"{progress}%"

                # Speed values are used as knots only when a valid
                # positive value is available from the API.
                if speed is not None and speed > 0:
                    eta_minutes = int((remaining_distance / speed) * 60)
                    hours, minutes = divmod(eta_minutes, 60)
                    eta_text = f"{hours}h {minutes}m"

        embed = discord.Embed(
            title=f"✈️ {username} • {callsign}",
            description=f"**{departure} → {arrival}**",
            color=discord.Color.from_rgb(45, 110, 190),
            timestamp=discord.utils.utcnow(),
        )

        avatar = flight.get("avatarUrl")
        if avatar and avatar.startswith("https://"):
            embed.set_thumbnail(url=avatar)

        embed.add_field(
            name="🛩️ Aircraft",
            value=(
                f"**Aircraft:** {aircraft_name}\n"
                f"**Livery:** {livery_name}\n"
                f"**Flight ID:** `{flight_id or 'N/A'}`"
            ),
            inline=False,
        )

        stats = (
            f"**Altitude:** {display_number(altitude)} ft\n"
            f"**Reported Speed:** {display_number(speed)}\n"
            f"**Position:** "
            f"{f'{lat:.4f}, {lon:.4f}' if lat is not None else 'N/A'}\n"
            f"**Progress (estimated):** {progress_text}\n"
            f"**Distance Remaining:** {remaining_text}\n"
            f"**ETA (estimated):** {eta_text}"
        )

        embed.add_field(
            name="📊 Live Flight Status",
            value=stats,
            inline=False,
        )

        embed.add_field(
            name="🧭 Flight Procedures",
            value=(
                f"**Departure / First Waypoint:** {departure}\n"
                f"**SID:** {sid}\n"
                f"**STAR:** {star}\n"
                f"**Approach:** {approach}\n"
                f"**Destination / Last Waypoint:** {arrival}"
            ),
            inline=False,
        )

        embed.add_field(
            name="🗺️ Filed Route",
            value=f"```text\n{route_text[:1000]}\n```",
            inline=False,
        )

        if plan_error:
            embed.add_field(
                name="ℹ️ Flight Plan",
                value=plan_error[:300],
                inline=False,
            )

        map_url = build_map_url(
            items,
            (lat, lon) if lat is not None and lon is not None else None,
        )

        if map_url:
            embed.set_image(url=map_url)

        embed.set_footer(
            text=(
                f"Flight {index + 1}/{total} • Expert Server • "
                "Akasa Air Virtual • Infinite Flight Live"
            )
        )

        return embed

    # ============================================================
    # COMMAND
    # ============================================================

    @app_commands.command(
        name="live",
        description="Track a live flight on the Infinite Flight Expert server.",
    )
    @app_commands.describe(
        query="Pilot username or callsign to search for",
    )
    @app_commands.guild_only()
    async def live(
        self,
        interaction: discord.Interaction,
        query: str,
    ):
        query = query.strip()

        if not query:
            return await interaction.response.send_message(
                "Enter a pilot username or callsign.",
                ephemeral=True,
            )

        if not IF_API_KEY:
            return await interaction.response.send_message(
                "❌ The Infinite Flight API key is not configured. "
                "Ask an administrator to set `IF_API_KEY` in Railway.",
                ephemeral=True,
            )

        await interaction.response.defer(thinking=True)

        session = await self.get_expert_session()

        if not session:
            return await interaction.followup.send(
                "⚠️ I couldn't find an active Expert server session, "
                "or the Infinite Flight API is unavailable.",
                ephemeral=True,
            )

        session_id = session.get("id")
        flights, status, error = await self.get_flights(session_id)

        if flights is None:
            return await interaction.followup.send(
                f"⚠️ Unable to retrieve live flights. "
                f"HTTP status: {status or 'unavailable'}.",
                ephemeral=True,
            )

        query_lower = query.casefold()

        def score(flight):
            username = (flight.get("username") or "").casefold()
            callsign = (flight.get("callsign") or "").casefold()

            if query_lower == callsign or query_lower == username:
                return 0
            if callsign.startswith(query_lower) or username.startswith(query_lower):
                return 1
            if query_lower in callsign or query_lower in username:
                return 2
            return 99

        matches = [
            flight
            for flight in flights
            if score(flight) < 99
        ]
        matches.sort(key=lambda flight: (score(flight), get_flight_label(flight)))

        if not matches:
            return await interaction.followup.send(
                f"⚠️ No active Expert Server flights matched `{query}`.",
                ephemeral=True,
            )

        view = LiveFlightView(
            cog=self,
            session_id=session_id,
            matches=matches,
            index=0,
            query=query,
        )

        embed = await view.build_embed()

        await interaction.followup.send(
            embed=embed,
            view=view,
        )


# ================================================================
# PAGINATION / REFRESH VIEW
# ================================================================

class LiveFlightView(discord.ui.View):
    def __init__(
        self,
        cog: Live,
        session_id: str,
        matches: list,
        index: int = 0,
        query: str = "",
    ):
        super().__init__(timeout=300)

        self.cog = cog
        self.session_id = session_id
        self.matches = matches
        self.index = index
        self.query = query

        self._update_buttons()

    def _update_buttons(self):
        self.previous_button.disabled = (
            len(self.matches) <= 1 or self.index <= 0
        )
        self.next_button.disabled = (
            len(self.matches) <= 1 or self.index >= len(self.matches) - 1
        )

    async def build_embed(self):
        return await self.cog.build_flight_embed(
            self.session_id,
            self.matches[self.index],
            self.index,
            len(self.matches),
        )

    async def interaction_check(self, interaction: discord.Interaction):
        # The original user controls this private tracker.
        if interaction.message is None:
            return True

        # Ephemeral views are only visible to their creator, but this
        # additional check prevents others from using copied controls.
        if interaction.user.bot:
            await private_view_error(interaction, "Bots cannot control this tracker.")
            return False

        return True

    @discord.ui.button(
        label="◀ Previous",
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def previous_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.index = max(0, self.index - 1)
        self._update_buttons()

        await interaction.response.defer()
        embed = await self.build_embed()
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(
        label="Next ▶",
        style=discord.ButtonStyle.secondary,
        row=0,
    )
    async def next_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.index = min(len(self.matches) - 1, self.index + 1)
        self._update_buttons()

        await interaction.response.defer()
        embed = await self.build_embed()
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(
        label="🔄 Refresh",
        style=discord.ButtonStyle.primary,
        row=1,
    )
    async def refresh_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.defer()

        flights, status, error = await self.cog.get_flights(self.session_id)

        if flights is None:
            return await interaction.followup.send(
                f"⚠️ Refresh failed. HTTP status: {status or 'unavailable'}.",
                ephemeral=True,
            )

        # Prefer the same flight ID so pagination never silently switches
        # the user to a different pilot after a refresh.
        old_flight = self.matches[self.index]
        old_id = get_flight_id(old_flight)

        updated = next(
            (
                flight for flight in flights
                if old_id and get_flight_id(flight) == old_id
            ),
            None,
        )

        if updated:
            self.matches[self.index] = updated
        else:
            # Flight may have left the server. Search the original query.
            query_lower = self.query.casefold()

            matches = [
                flight for flight in flights
                if query_lower in (flight.get("username") or "").casefold()
                or query_lower in (flight.get("callsign") or "").casefold()
            ]

            if not matches:
                return await interaction.followup.send(
                    "⚠️ This flight is no longer active on the Expert server.",
                    ephemeral=True,
                )

            self.matches = matches
            self.index = min(self.index, len(matches) - 1)

        self._update_buttons()
        embed = await self.build_embed()

        await interaction.edit_original_response(
            embed=embed,
            view=self,
        )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


async def private_view_error(
    interaction: discord.Interaction,
    message: str,
):
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


# ================================================================
# EXTENSION SETUP
# ================================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(Live(bot))
