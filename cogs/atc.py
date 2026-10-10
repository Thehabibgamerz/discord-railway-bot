
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


async def api_get(session, endpoint):
    """Request data from the Infinite Flight API."""

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


async def get_expert_session(session):
    """Find the active Expert Server session."""

    sessions = await api_get(session, "sessions")

    expert_sessions = [
        item for item in sessions
        if isinstance(item, dict)
        and "expert" in item.get("name", "").lower()
        and item.get("id")
    ]

    if not expert_sessions:
        raise RuntimeError("No active Expert Server session was found.")

    # Prefer an exact Expert name if multiple results are returned.
    expert_sessions.sort(
        key=lambda item: (
            item.get("name", "").strip().lower() != "expert"
        )
    )

    return expert_sessions[0]


async def get_atc_data():
    """Fetch the Expert session and its live ATC list."""

    if not IF_API_KEY:
        raise RuntimeError(
            "IF_API_KEY is missing from your environment variables."
        )

    async with aiohttp.ClientSession(
        timeout=REQUEST_TIMEOUT
    ) as session:
        expert = await get_expert_session(session)
        controllers = await api_get(
            session,
            f"sessions/{expert['id']}/atc",
        )

    if not isinstance(controllers, list):
        raise RuntimeError("Unexpected ATC data format.")

    return expert, controllers


def get_airport_name(controller):
    """Return the airport identifier supplied by the API."""

    airport = controller.get("airportName")
    if isinstance(airport, str):
        return airport.strip().upper()
    return ""


def count_airports(controllers):
    """Count active controllers at each airport."""

    counts = {}

    for controller in controllers:
        airport = get_airport_name(controller)
        if airport:
            counts[airport] = counts.get(airport, 0) + 1

    return sorted(counts.items())


def get_active_time(controller):
    """Convert a controller start timestamp to a readable duration."""

    start_time = controller.get("startTime")

    if not start_time:
        return "N/A"

    try:
        if isinstance(start_time, (int, float)):
            start_dt = datetime.fromtimestamp(
                start_time, tz=timezone.utc
            )
        else:
            start_dt = datetime.fromisoformat(
                str(start_time).replace("Z", "+00:00")
            )

            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)

            start_dt = start_dt.astimezone(timezone.utc)

        seconds = max(
            0,
            int(
                (
                    datetime.now(timezone.utc) - start_dt
                ).total_seconds()
            ),
        )

        hours, remainder = divmod(seconds, 3600)
        minutes = remainder // 60

        if hours:
            return f"{hours}h {minutes:02d}m"

        return f"{minutes}m"

    except (ValueError, TypeError, OverflowError, OSError):
        return "N/A"


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


def build_airport_embed(airport, controllers, session_name):
    """Create an embed showing all current controllers at one airport."""

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

    # Build a compact, readable controller table.
    rows = []

    sorted_controllers = sorted(
        controllers,
        key=lambda item: (
            get_facility(item).lower(),
            str(item.get("username", "Unknown")).lower(),
        ),
    )

    for controller in sorted_controllers:
        facility = get_facility(controller)
        username = str(controller.get("username") or "Unknown")
        active = get_active_time(controller)

        # Keep each row compact enough for Discord embeds.
        if len(username) > 24:
            username = username[:21] + "..."

        rows.append(
            f"{facility[:14]:<14}  {username:<24}  {active:>7}"
        )

    header = f"{'Facility':<14}  {'Controller':<24}  {'Online':>7}"
    lines = [header, "-" * len(header)]

    for row in rows:
        candidate = lines + [row]

        # Embed field values have a 1024-character limit.
        if len("```text\n" + "\n".join(candidate) + "\n```") > 1000:
            lines.append("... additional controllers omitted")
            break

        lines.append(row)

    embed.add_field(
        name="📋 Active Controllers",
        value="```text\n" + "\n".join(lines) + "\n```",
        inline=False,
    )

    # Show a map link when valid coordinates are available.
    location = next(
        (
            controller
            for controller in sorted_controllers
            if isinstance(controller.get("latitude"), (int, float))
            and isinstance(controller.get("longitude"), (int, float))
            and -90 <= controller["latitude"] <= 90
            and -180 <= controller["longitude"] <= 180
        ),
        None,
    )

    if location:
        embed.add_field(
            name="📍 Airport Map",
            value=(
                f"[Open location in Google Maps]"
                f"(https://www.google.com/maps?q="
                f"{location['latitude']},{location['longitude']})"
            ),
            inline=False,
        )

    embed.set_footer(
        text="Akasa Air Virtual • Infinite Flight Live • Expert Server"
    )

    return embed


class ATCView(discord.ui.View):
    """Airport selector and refresh button for the Expert Server."""

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

        self.refresh_button.disabled = selected_airport is None

    async def refresh_data(self, interaction):
        """Refresh the airport list and update the current message."""

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            expert, controllers = await get_atc_data()
        except RuntimeError as exc:
            return await interaction.followup.send(
                f"⚠️ {exc}",
                ephemeral=True,
            )
        except asyncio.TimeoutError:
            return await interaction.followup.send(
                "⏱️ Infinite Flight API timed out. Please try again.",
                ephemeral=True,
            )
        except aiohttp.ClientError:
            return await interaction.followup.send(
                "🌐 Could not connect to Infinite Flight API.",
                ephemeral=True,
            )

        self.session_id = expert["id"]
        self.session_name = expert.get("name", "Expert")
        self.airports = count_airports(controllers)

        if not self.selected_airport:
            view = ATCView(
                self.session_id,
                self.session_name,
                self.airports,
            )

            note = (
                f"Showing the first 25 of {len(self.airports)} airports."
                if len(self.airports) > 25
                else "Select an airport to view its active controllers."
            )

            await interaction.message.edit(
                content=(
                    f"🟠 **Expert Server ATC**\n{note}"
                    if self.airports
                    else "⚠️ No active ATC controllers on the Expert Server."
                ),
                embed=None,
                view=view if self.airports else None,
            )

            return await interaction.followup.send(
                "✅ ATC airport list refreshed.",
                ephemeral=True,
            )

        controllers_here = [
            controller for controller in controllers
            if get_airport_name(controller) == self.selected_airport
        ]

        if not controllers_here:
            embed = discord.Embed(
                title=f"🎙️ Live ATC — {self.selected_airport}",
                description=(
                    "No active controllers are currently listed at this "
                    "airport on the Expert Server."
                ),
                color=EXPERT_COLOR,
            )

            view = ATCView(
                self.session_id,
                self.session_name,
                self.airports,
            )

            await interaction.message.edit(
                embed=embed,
                view=view if self.airports else None,
            )

            return await interaction.followup.send(
                f"ℹ️ No active controllers remain at "
                f"**{self.selected_airport}**.",
                ephemeral=True,
            )

        embed = build_airport_embed(
            self.selected_airport,
            controllers_here,
            self.session_name,
        )

        view = ATCView(
            self.session_id,
            self.session_name,
            self.airports,
            self.selected_airport,
        )

        await interaction.message.edit(embed=embed, view=view)

        await interaction.followup.send(
            f"✅ ATC data for **{self.selected_airport}** refreshed.",
            ephemeral=True,
        )

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
        await self.refresh_data(interaction)


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
        await interaction.response.defer(ephemeral=True, thinking=True)

        airport = self.values[0]

        try:
            expert, controllers = await get_atc_data()
        except RuntimeError as exc:
            return await interaction.followup.send(
                f"⚠️ {exc}",
                ephemeral=True,
            )
        except asyncio.TimeoutError:
            return await interaction.followup.send(
                "⏱️ Infinite Flight API timed out. Please try again.",
                ephemeral=True,
            )
        except aiohttp.ClientError:
            return await interaction.followup.send(
                "🌐 Could not connect to Infinite Flight API.",
                ephemeral=True,
            )

        airport_controllers = [
            controller for controller in controllers
            if get_airport_name(controller) == airport
        ]

        airports = count_airports(controllers)

        if not airport_controllers:
            view = ATCView(
                expert["id"],
                expert.get("name", "Expert"),
                airports,
            )

            await interaction.message.edit(
                content=f"⚠️ No active controllers remain at **{airport}**.",
                embed=None,
                view=view if airports else None,
            )

            return await interaction.followup.send(
                f"No active controllers found at **{airport}**.",
                ephemeral=True,
            )

        session_name = expert.get("name", "Expert")
        embed = build_airport_embed(
            airport,
            airport_controllers,
            session_name,
        )

        view = ATCView(
            expert["id"],
            session_name,
            airports,
            airport,
        )

        await interaction.message.edit(
            content=None,
            embed=embed,
            view=view,
        )

        await interaction.followup.send(
            f"✅ Showing active ATC at **{airport}**.",
            ephemeral=True,
        )


class ATC(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="atc",
        description="View live airport ATC on the Infinite Flight Expert Server",
    )
    @app_commands.guild_only()
    async def atc(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            expert, controllers = await get_atc_data()
        except RuntimeError as exc:
            return await interaction.followup.send(
                f"⚠️ {exc}",
                ephemeral=True,
            )
        except asyncio.TimeoutError:
            return await interaction.followup.send(
                "⏱️ Infinite Flight API timed out. Please try again.",
                ephemeral=True,
            )
        except aiohttp.ClientError:
            return await interaction.followup.send(
                "🌐 Could not connect to Infinite Flight API.",
                ephemeral=True,
            )

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
