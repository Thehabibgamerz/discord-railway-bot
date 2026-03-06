import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
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

class FeaturedRoutes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.post_routes.start()

    def cog_unload(self):
        self.post_routes.cancel()

    @tasks.loop(seconds=60)
    async def post_routes(self):
        now = datetime.now() + IST_OFFSET
        if now.hour == 0 and now.minute == 0:  # Midnight IST
            weekday = now.strftime("%A").lower()
            routes = load_routes()
            if weekday in routes:
                channel_id = routes[weekday].get("channel_id")
                channel = self.bot.get_channel(channel_id)
                if channel:
                    role_id = routes[weekday].get("role_ping")
                    mention_text = f"<@&{role_id}>" if role_id else ""
                    multiplier = routes[weekday].get("multiplier", "1x")
                    flight_lines = []
                    for flight in routes[weekday]["flights"]:
                        code = flight.get("code")
                        route = flight.get("route")
                        duration = flight.get("duration")
                        aircraft = flight.get("aircraft")
                        flight_lines.append(f"`{code}` — {route} | {duration} | {aircraft}")
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
                    await channel.send(content=mention_text, embed=embed)

    @post_routes.before_loop
    async def before_post_routes(self):
        await self.bot.wait_until_ready()

    # Staff-only: add/update day flights
    @app_commands.command(name="setroute", description="Add a flight to a day")
    @app_commands.describe(
        day="Day of week",
        code="Flight code",
        route="Route (e.g., VOBL → VIDP)",
        duration="Flight duration (e.g., 5h10m)",
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
        routes = load_routes()
        if day_lower not in routes:
            routes[day_lower] = {"channel_id": channel.id, "flights": [], "multiplier": multiplier, "role_ping": role_ping.id if role_ping else None}
        else:
            routes[day_lower]["channel_id"] = channel.id
            routes[day_lower]["multiplier"] = multiplier
            if role_ping:
                routes[day_lower]["role_ping"] = role_ping.id

        routes[day_lower]["flights"].append({
            "code": code,
            "route": route,
            "duration": duration,
            "aircraft": aircraft
        })
        save_routes(routes)
        await interaction.response.send_message(f"✅ Flight added for {day.title()}", ephemeral=True)

    # Staff-only: clear day
    @app_commands.command(name="clearroutes", description="Clear all flights for a day")
    @app_commands.describe(day="Day of week to clear")
    async def clearroutes(self, interaction: discord.Interaction, day: str):
        if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("Only staff can clear routes.", ephemeral=True)
            return

        day_lower = day.strip().lower()
        routes = load_routes()
        if day_lower in routes:
            routes.pop(day_lower)
            save_routes(routes)
            await interaction.response.send_message(f"✅ Cleared routes for {day.title()}", ephemeral=True)
        else:
            await interaction.response.send_message(f"No routes scheduled for {day.title()}", ephemeral=True)

    # Weekly schedule preview
    @app_commands.command(name="weeklyroutes", description="View all routes for the week")
    @app_commands.describe(ping_role="Optional role to ping in weekly schedule")
    async def weeklyroutes(self, interaction: discord.Interaction, ping_role: discord.Role = None):
        routes = load_routes()
        if not routes:
            await interaction.response.send_message("No routes scheduled yet.", ephemeral=True)
            return

        embed = discord.Embed(title="🗓️ Weekly Featured Routes", color=discord.Color.orange())
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            if day in routes:
                multiplier = routes[day].get("multiplier", "1x")
                flight_lines = []
                for flight in routes[day]["flights"]:
                    flight_lines.append(f"`{flight.get('code')}` — {flight.get('route')} | {flight.get('duration')} | {flight.get('aircraft')}")
                flight_text = "\n".join(flight_lines) if flight_lines else "No flights scheduled"
                description = (
                    f"All pilots are eligible to fly the following featured routes. "
                    f"These flights offer a {multiplier} multiplier, making it a great opportunity to maximize your rewards. "
                    f"Ensure compliance with airline procedures and standard operating practices.\n\n"
                    f"{flight_text}"
                )
                embed.add_field(name=f"{day.title()}", value=description, inline=False)
            else:
                embed.add_field(name=day.title(), value="No flights scheduled", inline=False)

        mention_text = ping_role.mention if ping_role else ""
        await interaction.response.send_message(content=mention_text, embed=embed)

async def setup(bot):
    await bot.add_cog(FeaturedRoutes(bot))
