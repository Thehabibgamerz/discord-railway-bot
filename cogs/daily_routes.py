import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import json
import os

ROUTES_FILE = "daily_routes.json"
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

class DailyRoutes(commands.Cog):
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
                    for route in routes[weekday]["routes"]:
                        embed = discord.Embed(
                            title=f"🛫 Featured Route - {weekday.title()}",
                            description=route.get("description", "No description"),
                            color=discord.Color.orange()
                        )
                        embed.add_field(name="Route", value=route.get("route", "Unknown"), inline=False)
                        if route.get("image"):
                            embed.set_image(url=route.get("image"))
                        await channel.send(content=mention_text, embed=embed)

    @post_routes.before_loop
    async def before_post_routes(self):
        await self.bot.wait_until_ready()

    # Staff-only: add/update route
    @app_commands.command(name="setdailyroute", description="Set featured route for a specific day")
    @app_commands.describe(
        day="Day of week (Monday, Tuesday...)",
        route="Route name",
        description="Route description",
        channel="Channel to post",
        image="Optional image",
        role_ping="Role to ping when route posts (optional)"
    )
    async def setdailyroute(
        self,
        interaction: discord.Interaction,
        day: str,
        route: str,
        description: str,
        channel: discord.TextChannel,
        image: str = None,
        role_ping: discord.Role = None
    ):
        if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("Only staff can set daily routes.", ephemeral=True)
            return

        day_lower = day.strip().lower()
        routes = load_routes()
        if day_lower not in routes:
            routes[day_lower] = {"channel_id": channel.id, "routes": [], "role_ping": role_ping.id if role_ping else None}
        else:
            routes[day_lower]["channel_id"] = channel.id
            if role_ping:
                routes[day_lower]["role_ping"] = role_ping.id

        routes[day_lower]["routes"].append({
            "route": route,
            "description": description,
            "image": image
        })
        save_routes(routes)
        await interaction.response.send_message(f"✅ Route added for {day.title()}", ephemeral=True)

    # Staff-only: clear day
    @app_commands.command(name="cleardailyroute", description="Clear routes for a specific day")
    @app_commands.describe(day="Day of week to clear")
    async def cleardailyroute(self, interaction: discord.Interaction, day: str):
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
            await interaction.response.send_message(f"No routes found for {day.title()}", ephemeral=True)

    # Weekly schedule preview
    @app_commands.command(name="weeklyroutes", description="View all scheduled routes for the week")
    @app_commands.describe(ping_role="Optional role to ping in weekly schedule")
    async def weeklyroutes(self, interaction: discord.Interaction, ping_role: discord.Role = None):
        routes = load_routes()
        if not routes:
            await interaction.response.send_message("No routes scheduled yet.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🗓️ Weekly Featured Routes",
            color=discord.Color.orange()
        )

        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            if day in routes:
                desc_lines = []
                for route in routes[day]["routes"]:
                    line = f"**{route.get('route')}** - {route.get('description', 'No description')}"
                    desc_lines.append(line)
                desc_text = "\n".join(desc_lines)
                embed.add_field(name=day.title(), value=desc_text, inline=False)
            else:
                embed.add_field(name=day.title(), value="No routes scheduled", inline=False)

        mention_text = ping_role.mention if ping_role else ""
        await interaction.response.send_message(content=mention_text, embed=embed)

async def setup(bot):
    await bot.add_cog(DailyRoutes(bot))
