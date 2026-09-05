import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select
from supabase import create_client, Client
from datetime import datetime, timezone
import os

LIVE_FLIGHTS_CHANNEL_ID = 1545409171057414204

SUPABASE_URL = "https://xljanwcgesjhdoaavmuo.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

STATUSES = [
    ("🔧", "Pre-flight"),
    ("🛫", "Departing"),
    ("📈", "Climbing"),
    ("✈️", "Cruise"),
    ("📉", "Descending"),
    ("🛬", "Approaching"),
    ("🛟", "Landing"),
    ("🅿️", "Parked"),
]


def get_db() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ================= SUPABASE HELPERS =================

def db_create_flight(data: dict) -> dict:
    res = get_db().table("live_flights").insert(data).execute()
    return res.data[0] if res.data else {}


def db_get_flight(flight_id: int) -> dict | None:
    try:
        res = get_db().table("live_flights").select("*").eq("id", flight_id).single().execute()
        return res.data
    except Exception:
        return None


def db_update_status(flight_id: int, status: str):
    get_db().table("live_flights").update({"status": status}).eq("id", flight_id).execute()


def db_set_message_id(flight_id: int, message_id: int):
    get_db().table("live_flights").update({"message_id": message_id}).eq("id", flight_id).execute()


def db_end_flight(flight_id: int):
    get_db().table("live_flights").update({"active": False}).eq("id", flight_id).execute()


def db_get_active_flights(guild_id: int):
    try:
        res = get_db().table("live_flights").select("*").eq("guild_id", guild_id).eq("active", True).order("created_at").execute()
        return res.data or []
    except Exception:
        return []


# ================= MESSAGE BUILDER =================

def build_flight_text(flight: dict) -> str:
    status_emoji = next((e for e, s in STATUSES if s == flight["status"]), "✈️")
    note_line = f"\n📝 **Note:** {flight['note']}" if flight.get("note") else ""

    return (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✈️ **LIVE FLIGHT UPDATE**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 **Pilot:** {flight['pilot_name']}\n"
        f"🔢 **Flight Number:** {flight['flight_number']}\n"
        f"🗺️ **Route:** {flight['departure']} → {flight['arrival']}\n"
        f"🛩️ **Aircraft:** {flight['aircraft']}\n"
        f"⏱️ **Flight Time:** {flight['flight_time']}\n"
        f"{status_emoji} **Status:** {flight['status']}\n"
        f"{note_line}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )


# ================= STATUS VIEW =================

class StatusSelectMenu(Select):
    def __init__(self, flight_id: int, pilot_id: int):
        self.flight_id = flight_id
        self.pilot_id = pilot_id

        options = [
            discord.SelectOption(
                label=status,
                emoji=emoji,
                value=status
            )
            for emoji, status in STATUSES
        ]

        super().__init__(
            placeholder="Update flight status...",
            options=options,
            custom_id=f"lf_status:{flight_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.pilot_id:
            return await interaction.response.send_message(
                "❌ Only the pilot who posted this flight can update its status.", ephemeral=True
            )

        await interaction.response.defer()

        new_status = self.values[0]
        db_update_status(self.flight_id, new_status)

        flight = db_get_flight(self.flight_id)
        if not flight:
            return await interaction.followup.send("⚠️ Flight not found.", ephemeral=True)

        text = build_flight_text(flight)
        view = FlightView(self.flight_id, self.pilot_id)

        await interaction.message.edit(content=text, view=view)
        await interaction.followup.send(
            f"✅ Status updated to **{new_status}**", ephemeral=True
        )


class FlightView(View):
    def __init__(self, flight_id: int, pilot_id: int):
        super().__init__(timeout=None)
        self.add_item(StatusSelectMenu(flight_id, pilot_id))

        end_btn = Button(
            label="End Flight",
            emoji="🏁",
            style=discord.ButtonStyle.danger,
            custom_id=f"lf_end:{flight_id}"
        )
        end_btn.callback = self._end_callback(flight_id, pilot_id)
        self.add_item(end_btn)

    def _end_callback(self, flight_id: int, pilot_id: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != pilot_id:
                return await interaction.response.send_message(
                    "❌ Only the pilot who posted this flight can end it.", ephemeral=True
                )

            await interaction.response.defer()
            db_end_flight(flight_id)
            flight = db_get_flight(flight_id)

            if not flight:
                return await interaction.followup.send("⚠️ Flight not found.", ephemeral=True)

            ended_text = (
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏁 **FLIGHT COMPLETED**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **Pilot:** {flight['pilot_name']}\n"
                f"🔢 **Flight Number:** {flight['flight_number']}\n"
                f"🗺️ **Route:** {flight['departure']} → {flight['arrival']}\n"
                f"🛩️ **Aircraft:** {flight['aircraft']}\n"
                f"⏱️ **Flight Time:** {flight['flight_time']}\n"
                f"✅ **Status:** Flight Completed\n"
                f"━━━━━━━━━━━━━━━━━━━━━━"
            )

            disabled_view = View()
            disabled_select = Select(
                placeholder="Flight ended",
                options=[discord.SelectOption(label="Flight ended", value="ended")],
                disabled=True,
                custom_id=f"lf_ended:{flight_id}"
            )
            disabled_view.add_item(disabled_select)

            end_btn_disabled = Button(
                label="Flight Ended",
                emoji="🏁",
                style=discord.ButtonStyle.secondary,
                disabled=True,
                custom_id=f"lf_ended_btn:{flight_id}"
            )
            disabled_view.add_item(end_btn_disabled)

            await interaction.message.edit(content=ended_text, view=disabled_view)
            await interaction.followup.send("🏁 Flight ended. Safe skies!", ephemeral=True)

        return callback


# ================= COG =================

class LiveFlights(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="liveflights", description="Post your live flight to the live flights channel")
    @app_commands.describe(
        pilot_name="Your pilot name / IFC username",
        flight_number="Flight number (e.g. QP201)",
        route="Route in format VABB-VIDP",
        flight_time="Estimated flight time (e.g. 2h 30m)",
        aircraft="Aircraft type (e.g. Boeing 737 MAX 8)",
        status="Current flight status",
        note="Optional note or message"
    )
    @app_commands.choices(status=[
        app_commands.Choice(name="🔧 Pre-flight", value="Pre-flight"),
        app_commands.Choice(name="🛫 Departing", value="Departing"),
        app_commands.Choice(name="📈 Climbing", value="Climbing"),
        app_commands.Choice(name="✈️ Cruise", value="Cruise"),
        app_commands.Choice(name="📉 Descending", value="Descending"),
        app_commands.Choice(name="🛬 Approaching", value="Approaching"),
        app_commands.Choice(name="🛟 Landing", value="Landing"),
        app_commands.Choice(name="🅿️ Parked", value="Parked"),
    ])
    async def liveflights(
        self,
        interaction: discord.Interaction,
        pilot_name: str,
        flight_number: str,
        route: str,
        flight_time: str,
        aircraft: str,
        status: app_commands.Choice[str],
        note: str = None
    ):
        await interaction.response.defer(ephemeral=True)

        # Parse route
        parts = [p.strip().upper() for p in route.replace("→", "-").replace(">", "").split("-")]
        departure = parts[0] if len(parts) > 0 else route.upper()
        arrival = parts[1] if len(parts) > 1 else "N/A"

        try:
            record = db_create_flight({
                "guild_id": interaction.guild.id,
                "pilot_id": interaction.user.id,
                "pilot_name": pilot_name,
                "flight_number": flight_number.upper(),
                "departure": departure,
                "arrival": arrival,
                "flight_time": flight_time,
                "aircraft": aircraft,
                "status": status.value,
                "note": note,
                "active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:
            return await interaction.followup.send(f"❌ Failed to post flight: `{e}`", ephemeral=True)

        flight_id = record["id"]
        text = build_flight_text(record)
        view = FlightView(flight_id, interaction.user.id)

        channel = interaction.guild.get_channel(LIVE_FLIGHTS_CHANNEL_ID)
        if not channel:
            return await interaction.followup.send(
                "❌ Live flights channel not found. Contact staff.", ephemeral=True
            )

        try:
            msg = await channel.send(content=text, view=view)
            db_set_message_id(flight_id, msg.id)
        except discord.Forbidden:
            return await interaction.followup.send(
                "❌ I do not have permission to post in the live flights channel.", ephemeral=True
            )

        await interaction.followup.send(
            f"✅ Live flight posted in {channel.mention}!\nUse the **Update Status** dropdown on your post to update your progress.",
            ephemeral=True
        )

    @app_commands.command(name="activeflights", description="View all currently active live flights")
    async def activeflights(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        flights = db_get_active_flights(interaction.guild.id)

        if not flights:
            return await interaction.followup.send(
                "⚠️ No active live flights right now.", ephemeral=True
            )

        lines = [f"**Active Flights — {len(flights)} in the air**\n"]
        for f in flights:
            status_emoji = next((e for e, s in STATUSES if s == f["status"]), "✈️")
            lines.append(
                f"{status_emoji} **{f['flight_number']}** | {f['pilot_name']} | "
                f"{f['departure']} → {f['arrival']} | {f['aircraft']} | {f['status']}"
            )

        await interaction.followup.send("\n".join(lines), ephemeral=True)

    async def restore_views(self):
        flights = db_get_active_flights(0)  # 0 = all guilds
        for f in flights:
            if f.get("message_id"):
                try:
                    view = FlightView(f["id"], int(f["pilot_id"]))
                    self.bot.add_view(view, message_id=int(f["message_id"]))
                except Exception:
                    continue


async def setup(bot):
    cog = LiveFlights(bot)
    await bot.add_cog(cog)
    await cog.restore_views()
