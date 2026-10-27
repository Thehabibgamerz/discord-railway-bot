
# ============================================================
# AKASA AIR VIRTUAL — INFINITE FLIGHT WORLD MONITOR
# FILE: cogs/worldstatus.py
# Python 3.10.12 | discord.py 2.x | aiohttp
# PUBLIC DISCORD PANEL
# ============================================================

import os
import logging
from datetime import datetime, timezone

import aiohttp
import discord
from discord.ext import commands
from discord import app_commands

log = logging.getLogger(__name__)

BASE_URL = "https://api.infiniteflight.com/public/v2"
IF_API_KEY = os.getenv("IF_API_KEY")

WORLD_TYPES = {
    "Casual": 1,
    "Training": 2,
    "Expert": 3,
}

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
    11: "Unused",
}

ORANGE = discord.Color.from_rgb(240, 120, 37)
PAGE_SIZE = 10
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)


def safe_int(value):
    try:
        return int(value or 0)
    except (ValueError, TypeError):
        return 0


def airport_icao(airport):
    return str(airport.get("airportIcao") or "N/A").upper()


def traffic_total(airport):
    return (
        safe_int(airport.get("inboundFlightsCount"))
        + safe_int(airport.get("outboundFlightsCount"))
    )


def get_active_duration(start_raw):
    if not start_raw:
        return "N/A"

    try:
        value = start_raw.strip()

        if value.endswith("Z"):
            value = value[:-1] + "+00:00"

        started = datetime.fromisoformat(value)

        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)

        seconds = max(
            0,
            int(
                (
                    datetime.now(timezone.utc)
                    - started.astimezone(timezone.utc)
                ).total_seconds(),
            ),
        )

        hours, remainder = divmod(seconds, 3600)
        minutes = remainder // 60

        if hours:
            return f"{hours}h {minutes:02d}m"

        return f"{minutes}m"

    except (ValueError, TypeError, AttributeError):
        return "N/A"


def sort_airports(world_data, sort_mode):
    if sort_mode == "Inbound":
        key = lambda a: safe_int(a.get("inboundFlightsCount"))
    elif sort_mode == "Outbound":
        key = lambda a: safe_int(a.get("outboundFlightsCount"))
    elif sort_mode == "ATC":
        key = lambda a: len(a.get("atcFacilities") or [])
    elif sort_mode == "ICAO":
        return sorted(world_data, key=airport_icao)
    else:
        key = traffic_total

    return sorted(world_data, key=key, reverse=True)


def build_airport_embed(airport, server_choice):
    icao = airport_icao(airport)
    name = airport.get("airportName") or icao

    inbound = safe_int(airport.get("inboundFlightsCount"))
    outbound = safe_int(airport.get("outboundFlightsCount"))
    facilities = airport.get("atcFacilities") or []

    embed = discord.Embed(
        title=f"🌍 {name}",
        description=(
            f"**Airport:** `{icao}`\n"
            f"**Server:** {server_choice}\n"
            f"**Traffic status:** "
            f"{'Active' if inbound + outbound else 'Quiet'}"
        ),
        color=ORANGE,
        timestamp=datetime.now(timezone.utc),
    )

    embed.add_field(
        name="🛬 Inbound",
        value=f"**{inbound:,}**",
        inline=True,
    )
    embed.add_field(
        name="🛫 Outbound",
        value=f"**{outbound:,}**",
        inline=True,
    )
    embed.add_field(
        name="✈️ Total movements",
        value=f"**{inbound + outbound:,}**",
        inline=True,
    )
    embed.add_field(
        name="🎙️ Active ATC facilities",
        value=f"**{len(facilities)}**",
        inline=True,
    )

    if facilities:
        rows = []

        for facility in facilities:
            facility_type = FACILITY_TYPES.get(
                safe_int(facility.get("type")),
                "Unknown",
            )
            username = str(
                facility.get("username") or "Unlinked controller"
            ).replace("`", "'")[:60]

            duration = get_active_duration(
                facility.get("startTime")
            )

            rows.append(
                f"**{facility_type}** — {username}\n"
                f"└ Online: `{duration}`"
            )

        atc_text = "\n\n".join(rows)

        if len(atc_text) > 1024:
            atc_text = atc_text[:1000] + "\n…"

        embed.add_field(
            name="📡 Controller information",
            value=atc_text,
            inline=False,
        )
    else:
        embed.add_field(
            name="📡 Controller information",
            value="No active ATC facilities reported at this airport.",
            inline=False,
        )

    embed.set_footer(
        text=f"Akasa Air Virtual • Infinite Flight Live • {server_choice}"
    )

    return embed


def build_summary_embed(world_data, server_choice, page, sort_mode):
    airports = sort_airports(world_data, sort_mode)

    total_airports = len(world_data)
    total_inbound = sum(
        safe_int(a.get("inboundFlightsCount")) for a in world_data
    )
    total_outbound = sum(
        safe_int(a.get("outboundFlightsCount")) for a in world_data
    )
    total_atc = sum(
        len(a.get("atcFacilities") or []) for a in world_data
    )

    total_pages = max(
        1,
        (len(airports) + PAGE_SIZE - 1) // PAGE_SIZE,
    )
    page = max(0, min(page, total_pages - 1))

    start = page * PAGE_SIZE
    visible = airports[start:start + PAGE_SIZE]

    embed = discord.Embed(
        title=f"🌍 Infinite Flight — {server_choice} World Monitor",
        description=(
            f"Live world status for the **{server_choice} Server**.\n\n"
            f"🏢 **Active airports:** {total_airports:,}\n"
            f"🛬 **Inbound flights:** {total_inbound:,}\n"
            f"🛫 **Outbound flights:** {total_outbound:,}\n"
            f"🎙️ **Active ATC facilities:** {total_atc:,}\n"
            f"✈️ **Total movements:** "
            f"{total_inbound + total_outbound:,}"
        ),
        color=ORANGE,
        timestamp=datetime.now(timezone.utc),
    )

    if visible:
        lines = []

        for index, airport in enumerate(visible, start=start + 1):
            icao = airport_icao(airport)
            name = airport.get("airportName") or icao
            inbound = safe_int(airport.get("inboundFlightsCount"))
            outbound = safe_int(airport.get("outboundFlightsCount"))
            atc = len(airport.get("atcFacilities") or [])

            lines.append(
                f"**{index}. {icao}** — {name[:60]}\n"
                f"└ 🛬 {inbound} inbound · 🛫 {outbound} outbound"
                f" · 🎙️ {atc} ATC · **{inbound + outbound} total**"
            )

        embed.add_field(
            name=f"🏆 Airports · Page {page + 1}/{total_pages}",
            value="\n\n".join(lines)[:1024],
            inline=False,
        )

    embed.add_field(
        name="🔎 Controls",
        value=(
            "Select an airport to view traffic and ATC details.\n"
            "Use the dropdowns and buttons below to sort, browse, "
            "refresh, or switch servers."
        ),
        inline=False,
    )

    embed.set_footer(
        text=(
            f"Akasa Air Virtual • Sort: {sort_mode} • "
            "Infinite Flight Live API"
        )
    )

    return embed, page, total_pages


class WorldStatusView(discord.ui.View):
    def __init__(
        self,
        cog,
        owner_id,
        server_choice,
        session_id,
        world_data,
        page=0,
        sort_mode="Traffic",
        selected_icao=None,
    ):
        super().__init__(timeout=300)

        self.cog = cog
        self.owner_id = owner_id
        self.server_choice = server_choice
        self.session_id = session_id
        self.world_data = world_data
        self.page = page
        self.sort_mode = sort_mode
        self.selected_icao = selected_icao

        self.rebuild_controls()

    async def interaction_check(self, interaction):
        # The message is public, but only its creator can control it.
        # Everyone in the channel can still see the panel and its updates.
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "This panel is controlled by the person who opened it. "
                "Run `/worldstatus` to create your own panel.",
                ephemeral=True,
            )
            return False

        return True

    def rebuild_controls(self):
        self.clear_items()

        airports = sort_airports(
            self.world_data,
            self.sort_mode,
        )

        start = self.page * PAGE_SIZE
        visible = airports[start:start + PAGE_SIZE]

        if visible:
            self.add_item(AirportDropdown(self, visible))

        self.add_item(SortDropdown(self, self.sort_mode))
        self.add_item(PreviousPageButton(self))
        self.add_item(NextPageButton(self))
        self.add_item(RefreshButton(self))
        self.add_item(ServerButton(self))

    async def show_airport(self, interaction, icao):
        airport = next(
            (
                item for item in self.world_data
                if airport_icao(item) == icao
            ),
            None,
        )

        if airport is None:
            return await interaction.response.send_message(
                "⚠️ Airport data not found. Refresh and try again.",
                ephemeral=True,
            )

        self.selected_icao = icao
        self.rebuild_controls()

        await interaction.response.edit_message(
            embed=build_airport_embed(
                airport,
                self.server_choice,
            ),
            view=self,
        )

    async def refresh_panel(self, interaction):
        await interaction.response.defer()

        result = await self.cog.fetch_world(self.session_id)

        if result is None:
            return await interaction.followup.send(
                "⚠️ Refresh failed. The existing panel is unchanged.",
                ephemeral=True,
            )

        self.world_data = result
        self.selected_icao = None

        embed, self.page, _ = build_summary_embed(
            self.world_data,
            self.server_choice,
            self.page,
            self.sort_mode,
        )

        self.rebuild_controls()

        # Edits the original public message.
        await interaction.edit_original_response(
            embed=embed,
            view=self,
        )

    async def change_server(self, interaction, server_choice):
        await interaction.response.defer()

        session_id = await self.cog.fetch_session_id(server_choice)

        if not session_id:
            return await interaction.followup.send(
                f"⚠️ No active {server_choice} session found.",
                ephemeral=True,
            )

        world_data = await self.cog.fetch_world(session_id)

        if world_data is None:
            return await interaction.followup.send(
                "⚠️ Failed to fetch world data from Infinite Flight.",
                ephemeral=True,
            )

        self.server_choice = server_choice
        self.session_id = session_id
        self.world_data = world_data
        self.page = 0
        self.selected_icao = None

        embed, self.page, _ = build_summary_embed(
            self.world_data,
            self.server_choice,
            self.page,
            self.sort_mode,
        )

        self.rebuild_controls()

        # Keep the main panel public when switching servers.
        await interaction.edit_original_response(
            embed=embed,
            view=self,
        )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class AirportDropdown(discord.ui.Select):
    def __init__(self, parent, airports):
        self.parent_view = parent
        options = []

        for airport in airports:
            icao = airport_icao(airport)
            name = (airport.get("airportName") or icao)[:80]

            options.append(
                discord.SelectOption(
                    label=f"{icao} — {name}"[:100],
                    description=(
                        f"In {safe_int(airport.get('inboundFlightsCount'))}"
                        f" | Out {safe_int(airport.get('outboundFlightsCount'))}"
                        f" | ATC {len(airport.get('atcFacilities') or [])}"
                    )[:100],
                    value=icao,
                    default=(icao == parent.selected_icao),
                )
            )

        super().__init__(
            placeholder="🌍 Choose an airport...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )

    async def callback(self, interaction):
        await self.parent_view.show_airport(
            interaction,
            self.values[0],
        )


class SortDropdown(discord.ui.Select):
    def __init__(self, parent, current):
        self.parent_view = parent

        modes = [
            ("Traffic", "Highest combined traffic first"),
            ("Inbound", "Most inbound flights first"),
            ("Outbound", "Most outbound flights first"),
            ("ATC", "Most ATC facilities first"),
            ("ICAO", "Alphabetical airport ICAO"),
        ]

        options = [
            discord.SelectOption(
                label=label,
                description=description,
                value=label,
                default=(label == current),
            )
            for label, description in modes
        ]

        super().__init__(
            placeholder="📊 Sort airports...",
            min_values=1,
            max_values=1,
            options=options,
            row=1,
        )

    async def callback(self, interaction):
        self.parent_view.sort_mode = self.values[0]
        self.parent_view.page = 0
        self.parent_view.selected_icao = None

        embed, self.parent_view.page, _ = build_summary_embed(
            self.parent_view.world_data,
            self.parent_view.server_choice,
            self.parent_view.page,
            self.parent_view.sort_mode,
        )

        self.parent_view.rebuild_controls()

        await interaction.response.edit_message(
            embed=embed,
            view=self.parent_view,
        )


class PreviousPageButton(discord.ui.Button):
    def __init__(self, parent):
        super().__init__(
            label="Previous",
            emoji="⬅️",
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        self.parent_view = parent

    async def callback(self, interaction):
        self.parent_view.page = max(
            0,
            self.parent_view.page - 1,
        )
        self.parent_view.selected_icao = None

        embed, self.parent_view.page, _ = build_summary_embed(
            self.parent_view.world_data,
            self.parent_view.server_choice,
            self.parent_view.page,
            self.parent_view.sort_mode,
        )

        self.parent_view.rebuild_controls()

        await interaction.response.edit_message(
            embed=embed,
            view=self.parent_view,
        )


class NextPageButton(discord.ui.Button):
    def __init__(self, parent):
        super().__init__(
            label="Next",
            emoji="➡️",
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        self.parent_view = parent

    async def callback(self, interaction):
        _, current_page, total_pages = build_summary_embed(
            self.parent_view.world_data,
            self.parent_view.server_choice,
            self.parent_view.page,
            self.parent_view.sort_mode,
        )

        self.parent_view.page = min(
            current_page + 1,
            total_pages - 1,
        )
        self.parent_view.selected_icao = None

        embed, self.parent_view.page, _ = build_summary_embed(
            self.parent_view.world_data,
            self.parent_view.server_choice,
            self.parent_view.page,
            self.parent_view.sort_mode,
        )

        self.parent_view.rebuild_controls()

        await interaction.response.edit_message(
            embed=embed,
            view=self.parent_view,
        )


class RefreshButton(discord.ui.Button):
    def __init__(self, parent):
        super().__init__(
            label="Refresh",
            emoji="🔄",
            style=discord.ButtonStyle.success,
            row=2,
        )
        self.parent_view = parent

    async def callback(self, interaction):
        await self.parent_view.refresh_panel(interaction)


class ServerButton(discord.ui.Button):
    def __init__(self, parent):
        super().__init__(
            label="Change Server",
            emoji="🌐",
            style=discord.ButtonStyle.primary,
            row=2,
        )
        self.parent_view = parent

    async def callback(self, interaction):
        # Public server selection: no ephemeral response.
        await interaction.response.send_message(
            "🌐 Choose the server for this public world monitor:",
            view=ServerChoiceView(self.parent_view),
        )


class ServerChoiceView(discord.ui.View):
    def __init__(self, parent):
        super().__init__(timeout=60)
        self.parent_view = parent
        self.add_item(ServerChoiceDropdown(parent))

    async def interaction_check(self, interaction):
        if interaction.user.id != self.parent_view.owner_id:
            await interaction.response.send_message(
                "Only the panel owner can change its server.",
                ephemeral=True,
            )
            return False
        return True


class ServerChoiceDropdown(discord.ui.Select):
    def __init__(self, parent):
        self.parent_view = parent

        options = [
            discord.SelectOption(
                label=name,
                description=f"View the {name} server",
                emoji=emoji,
                value=name,
                default=(name == parent.server_choice),
            )
            for name, emoji in [
                ("Expert", "🟠"),
                ("Training", "🔵"),
                ("Casual", "🟢"),
            ]
        ]

        super().__init__(
            placeholder="Select server...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction):
        # Update the original public monitor message.
        # The selector itself is a public message too.
        await self.parent_view.change_server(
            interaction,
            self.values[0],
        )


class WorldStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.http = None

    async def cog_load(self):
        self.http = aiohttp.ClientSession(
            timeout=REQUEST_TIMEOUT,
            headers={"Accept": "application/json"},
        )

    async def cog_unload(self):
        if self.http and not self.http.closed:
            await self.http.close()

    async def api_get(self, endpoint):
        if not IF_API_KEY:
            log.error("IF_API_KEY environment variable is missing.")
            return None

        if self.http is None or self.http.closed:
            return None

        try:
            async with self.http.get(
                f"{BASE_URL}/{endpoint.lstrip('/')}",
                params={"apikey": IF_API_KEY},
            ) as response:
                if response.status != 200:
                    log.warning(
                        "Infinite Flight API HTTP %s for %s",
                        response.status,
                        endpoint,
                    )
                    return None

                data = await response.json(content_type=None)

                if not isinstance(data, dict):
                    return None

                if data.get("errorCode", 0) != 0:
                    log.warning(
                        "Infinite Flight API error for %s: %s",
                        endpoint,
                        data.get("errorCode"),
                    )
                    return None

                return data.get("result")

        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            log.warning("Infinite Flight request failed: %s", exc)
            return None

    async def fetch_session_id(self, server_choice):
        sessions = await self.api_get("sessions")

        if not isinstance(sessions, list):
            return None

        desired_type = WORLD_TYPES[server_choice]

        for session in sessions:
            if session.get("worldType") == desired_type:
                return session.get("id")

        # Fallback for API responses missing worldType.
        for session in sessions:
            if server_choice.lower() in (
                session.get("name") or ""
            ).lower():
                return session.get("id")

        return None

    async def fetch_world(self, session_id):
        result = await self.api_get(
            f"sessions/{session_id}/world"
        )

        return result if isinstance(result, list) else None

    @app_commands.command(
        name="worldstatus",
        description="View public Infinite Flight traffic and ATC status",
    )
    @app_commands.guild_only()
    async def worldstatus(self, interaction: discord.Interaction):
        if not IF_API_KEY:
            return await interaction.response.send_message(
                "⚠️ Infinite Flight API key is not configured. "
                "Set `IF_API_KEY` in Railway Variables.",
                ephemeral=True,
            )

        # PUBLIC initial response: do not defer ephemerally.
        await interaction.response.defer(thinking=True)

        server_choice = "Expert"
        session_id = await self.fetch_session_id(server_choice)

        if not session_id:
            return await interaction.followup.send(
                "⚠️ No active Expert session found, or the API is unavailable.",
            )

        world_data = await self.fetch_world(session_id)

        if world_data is None:
            return await interaction.followup.send(
                "⚠️ Failed to fetch Infinite Flight world data. Try again later.",
            )

        if not world_data:
            return await interaction.followup.send(
                "🌍 No active airport data was returned for Expert.",
            )

        view = WorldStatusView(
            cog=self,
            owner_id=interaction.user.id,
            server_choice=server_choice,
            session_id=session_id,
            world_data=world_data,
        )

        embed, view.page, _ = build_summary_embed(
            world_data,
            server_choice,
            0,
            "Traffic",
        )

        # PUBLIC follow-up: visible to everyone in the channel.
        await interaction.followup.send(
            embed=embed,
            view=view,
            ephemeral=False,
        )


async def setup(bot):
    await bot.add_cog(WorldStatus(bot))
