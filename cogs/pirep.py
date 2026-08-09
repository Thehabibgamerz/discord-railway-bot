import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
from supabase import create_client, Client
from datetime import datetime, timezone
import os

PIREP_LOG_CHANNEL_ID = 1481427245691043930

SUPABASE_URL = "https://xljanwcgesjhdoaavmuo.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


def get_db() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ================= SUPABASE HELPERS =================

def db_file_pirep(data: dict) -> dict:
    res = get_db().table("pireps").insert(data).execute()
    return res.data[0] if res.data else {}


def db_get_user_pireps(discord_id: int):
    try:
        res = get_db().table("pireps").select("*").eq("discord_id", discord_id).order("filed_at", desc=True).limit(10).execute()
        return res.data or []
    except Exception:
        return []


def db_get_all_pireps(limit: int = 20)
    try:
        res = get_db().table("pireps").select("*").order("filed_at", desc=True).limit(limit).execute()
        return res.data or []
    except Exception:
        return []


def db_get_pirep_stats(discord_id: int):
    try:
        res = get_db().table("pireps").select("flight_time_hours, flight_time_minutes").eq("discord_id", discord_id).execute()
        rows = res.data or []
        total_mins = sum(int(r.get("flight_time_hours", 0)) * 60 + int(r.get("flight_time_minutes", 0)) for r in rows)
        total_h, total_m = divmod(total_mins, 60)
        return len(rows), total_h, total_m
    except Exception:
        return 0, 0, 0


# ================= PIREP MODAL =================

class FilePIREPModal(Modal):
    def __init__(self):
        super().__init__(title="File a PIREP")

        self.flight_date = TextInput(
            label="Flight Date",
            placeholder="e.g. 2026-08-09",
            max_length=20
        )
        self.flight_number = TextInput(
            label="Flight Number",
            placeholder="e.g. QP101",
            max_length=20
        )
        self.route = TextInput(
            label="Departure → Arrival (ICAO)",
            placeholder="e.g. VABB → VIDP",
            max_length=20
        )
        self.aircraft = TextInput(
            label="Aircraft",
            placeholder="e.g. Boeing 737 MAX 8",
            max_length=50
        )
        self.flight_time = TextInput(
            label="Flight Time (e.g. 2h 30m) | Operator | Multiplier",
            placeholder="2h 30m | Akasa Air | 1.0x",
            max_length=60
        )

        self.add_item(self.flight_date)
        self.add_item(self.flight_number)
        self.add_item(self.route)
        self.add_item(self.aircraft)
        self.add_item(self.flight_time)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Parse route
        route_parts = [p.strip() for p in self.route.value.replace("→", "->").split("->")]
        departure = route_parts[0].upper() if len(route_parts) > 0 else "N/A"
        arrival = route_parts[1].upper() if len(route_parts) > 1 else "N/A"

        # Parse flight time, operator, multiplier from combined field
        ft_parts = [p.strip() for p in self.flight_time.value.split("|")]
        flight_time_raw = ft_parts[0] if len(ft_parts) > 0 else "0h 0m"
        operator = ft_parts[1] if len(ft_parts) > 1 else "N/A"
        multiplier = ft_parts[2] if len(ft_parts) > 2 else "1.0x"

        # Parse hours and minutes
        import re
        hours_match = re.search(r"(\d+)\s*h", flight_time_raw, re.IGNORECASE)
        mins_match = re.search(r"(\d+)\s*m", flight_time_raw, re.IGNORECASE)
        hours = int(hours_match.group(1)) if hours_match else 0
        minutes = int(mins_match.group(1)) if mins_match else 0

        now = datetime.now(timezone.utc).isoformat()

        pirep_data = {
            "discord_id": interaction.user.id,
            "discord_username": interaction.user.display_name,
            "flight_date": self.flight_date.value.strip(),
            "flight_number": self.flight_number.value.strip().upper(),
            "departure": departure,
            "arrival": arrival,
            "aircraft": self.aircraft.value.strip(),
            "operator": operator,
            "flight_time_hours": hours,
            "flight_time_minutes": minutes,
            "multiplier": multiplier,
            "filed_at": now
        }

        try:
            record = db_file_pirep(pirep_data)
            pirep_id = record.get("id", "N/A")
        except Exception as e:
            return await interaction.followup.send(
                f"❌ Failed to file PIREP: `{e}`", ephemeral=True
            )

        # Build confirmation embed
        embed = discord.Embed(
            title="✅ PIREP Filed Successfully",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="🆔 PIREP ID", value=f"`#{pirep_id}`", inline=True)
        embed.add_field(name="📅 Flight Date", value=self.flight_date.value.strip(), inline=True)
        embed.add_field(name="✈️ Flight Number", value=self.flight_number.value.strip().upper(), inline=True)
        embed.add_field(name="🛫 Departure", value=departure, inline=True)
        embed.add_field(name="🛬 Arrival", value=arrival, inline=True)
        embed.add_field(name="🛩️ Aircraft", value=self.aircraft.value.strip(), inline=True)
        embed.add_field(name="🏢 Operator", value=operator, inline=True)
        embed.add_field(name="⏱️ Flight Time", value=f"{hours}h {minutes}m", inline=True)
        embed.add_field(name="🎯 Multiplier", value=multiplier, inline=True)
        embed.set_footer(text=f"Filed by {interaction.user} • AkasaAirVirtual PIREP System")

        await interaction.followup.send(embed=embed, ephemeral=True)

        # Post to PIREP log channel
        log_channel = interaction.guild.get_channel(PIREP_LOG_CHANNEL_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="📋 New PIREP Filed",
                color=discord.Color.orange()
            )
            log_embed.set_thumbnail(url=interaction.user.display_avatar.url)
            log_embed.add_field(name="👤 Pilot", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="🆔 PIREP ID", value=f"`#{pirep_id}`", inline=True)
            log_embed.add_field(name="📅 Flight Date", value=self.flight_date.value.strip(), inline=True)
            log_embed.add_field(name="✈️ Flight Number", value=self.flight_number.value.strip().upper(), inline=True)
            log_embed.add_field(name="🗺️ Route", value=f"{departure} → {arrival}", inline=True)
            log_embed.add_field(name="🛩️ Aircraft", value=self.aircraft.value.strip(), inline=True)
            log_embed.add_field(name="🏢 Operator", value=operator, inline=True)
            log_embed.add_field(name="⏱️ Flight Time", value=f"{hours}h {minutes}m", inline=True)
            log_embed.add_field(name="🎯 Multiplier", value=multiplier, inline=True)
            log_embed.set_footer(
                text=f"Filed at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} • AkasaAirVirtual"
            )
            try:
                await log_channel.send(embed=log_embed)
            except discord.Forbidden:
                pass


# ================= PANEL VIEW =================

class PIREPPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="File PIREP", emoji="📋", style=discord.ButtonStyle.primary, custom_id="pirep_file")
    async def file_pirep(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(FilePIREPModal())

    @discord.ui.button(label="My PIREPs", emoji="📊", style=discord.ButtonStyle.secondary, custom_id="pirep_mylist")
    async def my_pireps(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)

        pireps = db_get_user_pireps(interaction.user.id)
        total, total_h, total_m = db_get_pirep_stats(interaction.user.id)

        embed = discord.Embed(
            title=f"📊 My PIREPs — {interaction.user.display_name}",
            description=f"**Total Flights:** {total} · **Total Hours:** {total_h}h {total_m}m",
            color=discord.Color.orange()
        )

        if pireps:
            for p in pireps[:8]:
                embed.add_field(
                    name=f"#{p.get('id')} — {p.get('flight_number', 'N/A')} | {p.get('flight_date', 'N/A')}",
                    value=(
                        f"🗺️ {p.get('departure')} → {p.get('arrival')} · "
                        f"🛩️ {p.get('aircraft')} · "
                        f"⏱️ {p.get('flight_time_hours')}h {p.get('flight_time_minutes')}m"
                    ),
                    inline=False
                )
        else:
            embed.description = "You have not filed any PIREPs yet."

        embed.set_footer(text="AkasaAirVirtual • PIREP System")
        await interaction.followup.send(embed=embed, ephemeral=True)


# ================= COG =================

class PIREPPanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="pirep_panel", description="Send the PIREP filing panel")
    @app_commands.describe(channel="Channel to post the panel in")
    async def pirep_panel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        embed = discord.Embed(
            title="📋 Akasa Air Virtual — PIREP System",
            description=(
                "Welcome to the **Flight Report (PIREP)** system.\n\n"
                "📋 **File PIREP** — Submit a new flight report\n"
                "📊 **My PIREPs** — View your flight history and total hours\n\n"
                "**Form fields:**\n"
                "• Flight Date · Flight Number · Route\n"
                "• Aircraft · Operator · Flight Time · Multiplier\n\n"
                "*File your PIREP after every completed flight.*"
            ),
            color=discord.Color.orange()
        )
        embed.set_footer(text="AkasaAirVirtual • PIREP System")

        view = PIREPPanelView()
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            f"✅ PIREP panel sent in {channel.mention}", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(PIREPPanel(bot))
    bot.add_view(PIREPPanelView())
