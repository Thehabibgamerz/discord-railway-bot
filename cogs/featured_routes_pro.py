import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
from datetime import datetime, timedelta
import asyncio
import json
import os

ROUTES_FILE = "weekly_routes.json"
STAFF_ROLE_ID = 1389824693388837035  # Staff role ID
IST_OFFSET = timedelta(hours=5, minutes=30)  # IST


def load_routes():
    if os.path.exists(ROUTES_FILE):
        with open(ROUTES_FILE, "r") as f:
            return json.load(f)
    return {}


def save_routes(routes):
    with open(ROUTES_FILE, "w") as f:
        json.dump(routes, f, indent=4)


class EditFlightModal(Modal):
    def __init__(self, cog, day, flight_index):
        super().__init__(title=f"Edit Flight - {day.title()}")
        self.cog = cog
        self.day = day
        self.flight_index = flight_index

        flight = cog.routes[day]["flights"][flight_index]
        self.code_input = TextInput(label="Flight Code", default=flight.get("code"))
        self.route_input = TextInput(label="Route", default=flight.get("route"))
        self.duration_input = TextInput(label="Duration", default=flight.get("duration"))
        self.aircraft_input = TextInput(label="Aircraft", default=flight.get("aircraft"))

        self.add_item(self.code_input)
        self.add_item(self.route_input)
        self.add_item(self.duration_input)
        self.add_item(self.aircraft_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.cog.routes[self.day]["flights"][self.flight_index] = {
            "code": self.code_input.value,
            "route": self.route_input.value,
            "duration": self.duration_input.value,
            "aircraft": self.aircraft_input.value
        }
        save_routes(self.cog.routes)
        await self.cog.update_dashboard(interaction.message)
        await interaction.response.send_message("✅ Flight updated!", ephemeral=True)


class FlightDashboardView(View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def update_dashboard(self, message: discord.Message):
        embed = discord.Embed(title="🗓️ Weekly Routes Dashboard", color=discord.Color.orange())
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            if day in self.cog.routes:
                flights = self.cog.routes[day].get("flights", [])
                flight_lines = [
                    f"`{f.get('code')}` — {f.get('route')} | {f.get('duration')} | {f.get('aircraft')}" 
                    for f in flights
                ]
                embed.add_field(name=day.title(), value="\n".join(flight_lines) if flight_lines else "No flights", inline=False)
            else:
                embed.add_field(name=day.title(), value="No flights", inline=False)
        await message.edit(embed=embed, view=self)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.primary)
    async def refresh(self, interaction: discord.Interaction, button: Button):
        if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("Only staff can refresh.", ephemeral=True)
            return
        await self.update_dashboard(interaction.message)
        await interaction.response.send_message("Dashboard refreshed!", ephemeral=True)


class FeaturedRoutesPro(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.routes = load_routes()
        self.post_routes.start()

    def cog_unload(self):
        self.post_routes.cancel()

    # ---------------- Daily Auto Post ---------------- #
    @tasks.loop(seconds=60)
    async def post_routes(self):
        now = datetime.now() + IST_OFFSET
        if now.hour == 0 and now.minute == 0:  # Midnight IST
            weekday = now.strftime("%A").lower()
            if weekday not in self.routes:
                return

            day_data = self.routes[weekday]
            channel = self.bot.get_channel(day_data["channel_id"])
            if not channel:
                return

            role_id = day_data.get("role_ping")
            mention_text = f"<@&{role_id}>" if role_id else ""
            multiplier = day_data.get("multiplier", "1x")
            flights = day_data.get("flights", [])

            flight_lines = [
                f"`{f.get('code')}` — {f.get('route')} | {f.get('duration')} | {f.get('aircraft')}" 
                for f in flights
            ]
            flight_text = "\n".join(flight_lines) if flight_lines else "No flights scheduled"

            description = (
                f"All pilots are eligible to fly the following featured routes. "
                f"These flights offer a {multiplier} multiplier, making it a great opportunity to maximize your rewards. "
                f"Ensure compliance with airline procedures and standard operating practices.\n\n"
                f"{flight_text}"
            )

            embed = discord.Embed(
                title=f"🗺️ Featured Routes — {weekday.title()}",
                description=description,
                color=discord.Color.orange()
            )

            message = await channel.send(content=mention_text, embed=embed)

            # Countdown updater (simple: first flight assumed at midnight)
            start_time = now
            if flights:
                asyncio.create_task(self.update_countdown(message, start_time, flights, multiplier))

    async def update_countdown(self, message: discord.Message, start_time: datetime, flights: list, multiplier: str):
        while True:
            now = datetime.now() + IST_OFFSET
            remaining = max(int((start_time - now).total_seconds()), 0)
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            seconds = remaining % 60

            flight_lines = [
                f"`{f.get('code')}` — {f.get('route')} | {f.get('duration')} | {f.get('aircraft')}" 
                for f in flights
            ]
            flight_text = "\n".join(flight_lines) if flight_lines else "No flights scheduled"
            countdown_text = f"⏱️ Next flight in: {hours}h {minutes}m {seconds}s\n\n"

            description = (
                f"All pilots are eligible to fly the following featured routes. "
                f"These flights offer a {multiplier} multiplier, making it a great opportunity to maximize your rewards. "
                f"Ensure compliance with airline procedures and standard operating practices.\n\n"
                f"{countdown_text}{flight_text}"
            )

            embed = discord.Embed(
                title=message.embeds[0].title,
                description=description,
                color=discord.Color.orange()
            )

            await message.edit(embed=embed)
            if remaining <= 0:
                break
            await asyncio.sleep(30)

    @post_routes.before_loop
    async def before_post_routes(self):
        await self.bot.wait_until_ready()

    # ---------------- Staff Commands ---------------- #

    @app_commands.command(name="setroute", description="Add a flight to a day")
    @app_commands.describe(
        day="Day of week",
        code="Flight code",
        route="Route (e.g., VOBL → VIDP)",
        duration="Flight duration",
        aircraft="Aircraft type",
        channel="Channel to post",
        multiplier="Multiplier (e.g., 2x)",
        role_ping="Optional role to ping"
    )
    async def setroute(
        self,
        interaction: discord.Interaction,
        day: str,
        code: str,
        route: str,
        duration: str,
        aircraft: str,
        channel: discord.TextChannel,
        multiplier: str = "1x",
        role_ping: discord.Role = None
    ):
        if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("Only staff can set routes.", ephemeral=True)
            return

        day_lower = day.strip().lower()
        if day_lower not in self.routes:
            self.routes[day_lower] = {
                "channel_id": channel.id,
                "flights": [],
                "multiplier": multiplier,
                "role_ping": role_ping.id if role_ping else None
            }
        else:
            self.routes[day_lower]["channel_id"] = channel.id
            self.routes[day_lower]["multiplier"] = multiplier
            if role_ping:
                self.routes[day_lower]["role_ping"] = role_ping.id

        self.routes[day_lower]["flights"].append({
            "code": code,
            "route": route,
            "duration": duration,
            "aircraft": aircraft
        })
        save_routes(self.routes)
        await interaction.response.send_message(f"✅ Flight added for {day.title()}", ephemeral=True)

    @app_commands.command(name="clearroutes", description="Clear all flights for a day")
    @app_commands.describe(day="Day of week")
    async def clearroutes(self, interaction: discord.Interaction, day: str):
        if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("Only staff can clear routes.", ephemeral=True)
            return

        day_lower = day.strip().lower()
        if day_lower in self.routes:
            self.routes.pop(day_lower)
            save_routes(self.routes)
            await interaction.response.send_message(f"✅ Cleared routes for {day.title()}", ephemeral=True)
        else:
            await interaction.response.send_message(f"No routes scheduled for {day.title()}", ephemeral=True)

    @app_commands.command(name="weeklyroutes", description="View weekly routes")
    @app_commands.describe(ping_role="Optional role to ping")
    async def weeklyroutes(self, interaction: discord.Interaction, ping_role: discord.Role = None):
        embed = discord.Embed(title="🗓️ Weekly Featured Routes", color=discord.Color.orange())
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            if day in self.routes:
                multiplier = self.routes[day].get("multiplier", "1x")
                flights = self.routes[day].get("flights", [])
                flight_lines = [
                    f"`{f.get('code')}` — {f.get('route')} | {f.get('duration')} | {f.get('aircraft')}" 
                    for f in flights
                ]
                flight_text = "\n".join(flight_lines) if flight_lines else "No flights"
                description = (
                    f"All pilots are eligible to fly the following featured routes. "
                    f"These flights offer a {multiplier} multiplier.\n\n{flight_text}"
                )
                embed.add_field(name=day.title(), value=description, inline=False)
            else:
                embed.add_field(name=day.title(), value="No flights scheduled", inline=False)

        mention_text = ping_role.mention if ping_role else ""
        await interaction.response.send_message(content=mention_text, embed=embed)

    # ---------------- Dashboard ---------------- #
    @app_commands.command(name="dashboard", description="View weekly routes dashboard")
    async def dashboard(self, interaction: discord.Interaction):
        if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("Only staff can access the dashboard.", ephemeral=True)
            return

        view = FlightDashboardView(self)
        embed = discord.Embed(title="🗓️ Weekly Routes Dashboard", color=discord.Color.orange())
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            if day in self.routes:
                flights = self.routes[day].get("flights", [])
                flight_lines = [
                    f"`{f.get('code')}` — {f.get('route')} | {f.get('duration')} | {f.get('aircraft')}" 
                    for f in flights
                ]
                embed.add_field(name=day.title(), value="\n".join(flight_lines) if flight_lines else "No flights", inline=False)
            else:
                embed.add_field(name=day.title(), value="No flights", inline=False)
        await interaction.response.send_message(embed=embed, view=view)

    # Dashboard update helper
    async def update_dashboard(self, message):
        view = FlightDashboardView(self)
        await view.update_dashboard(message)


async def setup(bot):
    await bot.add_cog(FeaturedRoutesPro(bot))
