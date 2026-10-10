
import os
import asyncio
from datetime import datetime, timezone

import aiohttp
import discord
from discord.ext import commands
from discord import app_commands


IF_API_KEY = os.getenv("IF_API_KEY")
BASE_URL = "https://api.infiniteflight.com/public/v2"

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)
EXPERT_COLOR = discord.Color.orange()

FACILITY_TYPES = {
    0: "Ground",
    1: "Tower",
    2: "Unicom",
    3: "Clearance",
    4: "Approach",
    5: "Departure",
    6: "Center",
    7: "ATIS",
}


# --------------------------------------------------
# INFINITE FLIGHT API
# --------------------------------------------------

async def api_get(session, endpoint):
    if not IF_API_KEY:
        raise RuntimeError(
            "IF_API_KEY is missing from Railway environment variables."
        )

    async with session.get(
        f"{BASE_URL}/{endpoint.lstrip('/')}",
        params={"apikey": IF_API_KEY},
    ) as response:

        if response.status == 401:
            raise RuntimeError("Invalid Infinite Flight API key.")

        if response.status == 429:
            raise RuntimeError(
                "Infinite Flight API rate limit reached. Try again shortly."
            )

        if response.status != 200:
            raise RuntimeError(
                f"Infinite Flight API returned HTTP {response.status}."
            )

        data = await response.json(content_type=None)

    if not isinstance(data, dict):
        raise RuntimeError("Unexpected response from Infinite Flight API.")

    if data.get("errorCode", 0) != 0:
        raise RuntimeError(
            data.get("errorMessage", "Infinite Flight API returned an error.")
        )

    return data.get("result", [])


async def get_atc_data():
    """Fetch the Expert Server session and live controllers."""

    if not IF_API_KEY:
        raise RuntimeError(
            "IF_API_KEY is missing from Railway environment variables."
        )

    async with aiohttp.ClientSession(
        timeout=REQUEST_TIMEOUT
    ) as session:

        sessions = await api_get(session, "sessions")

        expert_sessions = [
            item for item in sessions
            if isinstance(item, dict)
            and "expert" in item.get("name", "").lower()
            and item.get("id")
        ]

        if not expert_sessions:
            raise RuntimeError("No active Expert Server session was found.")

        expert_sessions.sort(
            key=lambda item: item.get("name", "").strip().lower() != "expert"
        )

        expert = expert_sessions[0]

        controllers = await api_get(
            session,
            f"sessions/{expert['id']}/atc",
        )

    if not isinstance(controllers, list):
        raise RuntimeError("Unexpected ATC data format.")

    return expert, controllers


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def get_airport_name(controller):
    airport = controller.get("airportName")

    if isinstance(airport, str):
        return airport.strip().upper()

    return ""


def count_airports(controllers):
    counts = {}

    for controller in controllers:
        airport = get_airport_name(controller)

        if airport:
            counts[airport] = counts.get(airport, 0) + 1

    return sorted(counts.items())


def get_facility(controller):
    facility_type = controller.get("type")

    try:
        facility_type = int(facility_type)
    except (TypeError, ValueError):
        pass

    return FACILITY_TYPES.get(
        facility_type,
        f"Type {facility_type}",
    )


def get_active_time(controller):
    start_time = controller.get("startTime")

    if not start_time:
        return "N/A"

    try:
        if isinstance(start_time, (int, float)):
            start_dt = datetime.fromtimestamp(
                start_time,
                tz=timezone.utc,
            )
        else:
            start_dt = datetime.fromisoformat(
                str(start_time).replace("Z", "+00:00")
            )

            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)

            start_dt = start_dt.astimezone(timezone.utc)

        elapsed = max(
            0,
            int(
                (
                    datetime.now(timezone.utc) - start_dt
                ).total_seconds()
            ),
        )

        hours, remainder = divmod(elapsed, 3600)
        minutes = remainder // 60

        if hours:
            return f"{hours}h {minutes:02d}m"

        return f"{minutes}m"

    except (ValueError, TypeError, OverflowError, OSError):
        return "N/A"


def get_map_url(controllers):
    """Return a Google Maps URL if valid coordinates are available."""

    for controller in controllers:
        latitude = controller.get("latitude")
        longitude = controller.get("longitude")

        if not isinstance(latitude, (int, float)):
            continue

        if not isinstance(longitude, (int, float)):
            continue

        if not (-90 <= latitude <= 90):
            continue

        if not (-180 <= longitude <= 180):
            continue

        return f"https://www.google.com/maps?q={latitude},{longitude}"

    return None


def build_airport_embed(airport, controllers, session_name):
    embed = discord.Embed(
        title=f"🎙️ Live ATC — {airport}",
        description=(
            f"**Server:** 🟠 {session_name}\n"
            f"**Airport:** `{airport}`\n"
            f"**Controllers online:** `{len(controllers)}`"
        ),
        color=EXPERT_COLOR,
        timestamp=discord.utils.utcnow(),
    )

    sorted_controllers = sorted(
        controllers,
        key=lambda item: (
            get_facility(item).lower(),
            str(item.get("username") or "Unknown").lower(),
        ),
    )

    header = f"{'Facility':<14}  {'Controller':<24}  {'Online':>7}"
    lines = [header, "-" * len(header)]

    for controller in sorted_controllers:
        facility = get_facility(controller)[:14]
        username = str(controller.get("username") or "Unknown")

        if len(username) > 24:
            username = username[:21] + "..."

        active = get_active_time(controller)

        lines.append(
            f"{facility:<14}  {username:<24}  {active:>7}"
        )

    # Stay within Discord's embed field size limit.
    displayed_lines = [lines[0], lines[1]]

    for line in lines[2:]:
        candidate = displayed_lines + [line, "... more controllers omitted"]

        if len("```text\n" + "\n".join(candidate) + "\n```") > 1000:
            displayed_lines.append("... more controllers omitted")
            break

        displayed_lines.append(line)

    embed.add_field(
        name="📋 Active Controllers",
        value="```text\n" + "\n".join(displayed_lines) + "\n```",
        inline=False,
    )

    map_url = get_map_url(sorted_controllers)

    if map_url:
        embed.add_field(
            name="📍 Airport Map",
            value=f"[Open in Google Maps]({map_url})",
            inline=False,
        )

    embed.set_footer(
        text="Akasa Air Virtual • Infinite Flight Live • Expert Server"
    )

    return embed


# --------------------------------------------------
# SAFE INTERACTION HELPERS
# --------------------------------------------------

async def acknowledge(interaction: discord.Interaction):
    """
    Acknowledge a component interaction without creating a separate
    'thinking' response. This allows the original message to be edited.
    """

    if not interaction.response.is_done():
        await interaction.response.defer()


async def report_error(interaction, message):
    """Send an error without leaving the interaction unacknowledged."""

    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                message,
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                message,
                ephemeral=True,
            )
    except discord.HTTPException:
        pass


async def safe_fetch_atc(interaction):
    """Fetch live data and handle common API failures."""

    try:
        return await get_atc_data()

    except RuntimeError as exc:
        await report_error(interaction, f"⚠️ {exc}")

    except asyncio.TimeoutError:
        await report_error(
            interaction,
            "⏱️ Infinite Flight API timed out. Please try again.",
        )

    except aiohttp.ClientError:
        await report_error(
            interaction,
            "🌐 Could not connect to the Infinite Flight API.",
        )

    except (ValueError, TypeError, KeyError):
        await report_error(
            interaction,
            "⚠️ Received an unexpected response from Infinite Flight.",
        )

    return None


# --------------------------------------------------
# AIRPORT SELECT MENU
# --------------------------------------------------

class ATCAirportSelect(discord.ui.Select):

    def __init__(self, parent_view, options):
        self.parent_view = parent_view

        super().__init__(
            placeholder="✈️ Select an ATC airport...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        # IMPORTANT: defer without thinking=True.
        await acknowledge(interaction)

        airport = self.values[0]

        result = await safe_fetch_atc(interaction)

        if result is None:
            return

        expert, controllers = result
        airport_controllers = [
            controller for controller in controllers
            if get_airport_name(controller) == airport
        ]

        airports = count_airports(controllers)
        session_name = expert.get("name", "Expert")

        if not airport_controllers:
            new_view = ATCView(
                expert["id"],
                session_name,
                airports,
            )

            await interaction.message.edit(
                content=(
                    f"⚠️ No active controllers remain at **{airport}**."
                ),
                embed=None,
                view=new_view if airports else None,
            )
            return

        embed = build_airport_embed(
            airport,
            airport_controllers,
            session_name,
        )

        new_view = ATCView(
            expert["id"],
            session_name,
            airports,
            selected_airport=airport,
        )

        # Update the original message. Do not create another response.
        await interaction.message.edit(
            content=None,
            embed=embed,
            view=new_view,
        )


# --------------------------------------------------
# ATC VIEW: DROPDOWN + REFRESH
# --------------------------------------------------

class ATCView(discord.ui.View):

    def __init__(
        self,
        session_id,
        session_name,
        airports,
        selected_airport=None,
    ):
        super().__init__(timeout=300)

        self.session_id = session_id
        self.session_name = session_name
        self.airports = airports
        self.selected_airport = selected_airport

        if airports:
            options = [
                discord.SelectOption(
                    label=airport,
                    description=f"{count} controller(s) online",
                    default=(airport == selected_airport),
                )
                for airport, count in airports[:25]
            ]

            self.add_item(ATCAirportSelect(self, options))

        self.refresh_button.disabled = False

    @discord.ui.button(
        label="Refresh ATC",
        emoji="🔄",
        style=discord.ButtonStyle.primary,
        row=1,
    )
    async def refresh_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        # Acknowledge immediately, but do not create a thinking message.
        await acknowledge(interaction)

        result = await safe_fetch_atc(interaction)

        if result is None:
            return

        expert, controllers = result
        airports = count_airports(controllers)
        session_name = expert.get("name", "Expert")

        # Refreshing the initial airport menu.
        if not self.selected_airport:
            new_view = ATCView(
                expert["id"],
                session_name,
                airports,
            )

            if airports:
                note = (
                    f"Showing the first 25 of {len(airports)} airports."
                    if len(airports) > 25
                    else "Select an airport to view its active controllers."
                )

                await interaction.message.edit(
                    content=f"🟠 **Expert Server ATC**\n{note}",
                    embed=None,
                    view=new_view,
                )
            else:
                await interaction.message.edit(
                    content=(
                        "🟠 No active ATC controllers were found "
                        "on the Expert Server."
                    ),
                    embed=None,
                    view=None,
                )

            return

        # Refreshing a selected airport.
        airport_controllers = [
            controller for controller in controllers
            if get_airport_name(controller) == self.selected_airport
        ]

        if not airport_controllers:
            new_view = ATCView(
                expert["id"],
                session_name,
                airports,
            )

            await interaction.message.edit(
                content=(
                    f"⚠️ No active controllers remain at "
                    f"**{self.selected_airport}**."
                ),
                embed=None,
                view=new_view if airports else None,
            )
            return

        embed = build_airport_embed(
            self.selected_airport,
            airport_controllers,
            session_name,
        )

        new_view = ATCView(
            expert["id"],
            session_name,
            airports,
            selected_airport=self.selected_airport,
        )

        await interaction.message.edit(
            content=None,
            embed=embed,
            view=new_view,
        )


# --------------------------------------------------
# MAIN /ATC COMMAND
# --------------------------------------------------

class ATC(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="atc",
        description=(
            "View live airport ATC on the Infinite Flight Expert Server"
        ),
    )
    @app_commands.guild_only()
    async def atc(self, interaction: discord.Interaction):
        await interaction.response.defer(
            ephemeral=True,
            thinking=False,
        )

        result = await safe_fetch_atc(interaction)

        if result is None:
            return

        expert, controllers = result
        airports = count_airports(controllers)

        if not airports:
            return await interaction.followup.send(
                "🟠 No active ATC controllers were found on the Expert Server.",
                ephemeral=True,
            )

        view = ATCView(
            expert["id"],
            expert.get("name", "Expert"),
            airports,
        )

        note = (
            f"Showing the first 25 of {len(airports)} airports."
            if len(airports) > 25
            else "Select an airport to view its active controllers."
        )

        await interaction.followup.send(
            content=f"🟠 **Expert Server ATC**\n{note}",
            view=view,
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(ATC(bot))
