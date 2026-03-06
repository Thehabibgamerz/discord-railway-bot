import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
import json
import os

ROUTES_FILE = "weekly_routes.json"
STAFF_ROLE_ID = 1389824693388837035  # Staff role ID

def load_routes():
    if os.path.exists(ROUTES_FILE):
        with open(ROUTES_FILE, "r") as f:
            return json.load(f)
    return {}

def save_routes(routes):
    with open(ROUTES_FILE, "w") as f:
        json.dump(routes, f, indent=4)

class EditRouteModal(Modal):
    def __init__(self, dashboard, day, flight_index):
        super().__init__(title=f"Edit Flight - {day.title()}")
        self.dashboard = dashboard
        self.day = day
        self.flight_index = flight_index

        flight = dashboard.routes[day]["flights"][flight_index]

        self.code_input = TextInput(label="Flight Code", default=flight.get("code"))
        self.route_input = TextInput(label="Route", default=flight.get("route"))
        self.duration_input = TextInput(label="Duration", default=flight.get("duration"))
        self.aircraft_input = TextInput(label="Aircraft", default=flight.get("aircraft"))

        self.add_item(self.code_input)
        self.add_item(self.route_input)
        self.add_item(self.duration_input)
        self.add_item(self.aircraft_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.dashboard.routes[self.day]["flights"][self.flight_index] = {
            "code": self.code_input.value,
            "route": self.route_input.value,
            "duration": self.duration_input.value,
            "aircraft": self.aircraft_input.value
        }
        save_routes(self.dashboard.routes)
        await self.dashboard.update_dashboard(interaction.message)
        await interaction.response.send_message("✅ Flight updated!", ephemeral=True)

class WeeklyRoutesDashboardView(View):
    def __init__(self, routes):
        super().__init__(timeout=None)
        self.routes = routes

    async def update_dashboard(self, message):
        embed = discord.Embed(title="🗓️ Weekly Routes Dashboard", color=discord.Color.orange())
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            if day in self.routes:
                flights = self.routes[day].get("flights", [])
                flight_lines = [f"`{f.get('code')}` — {f.get('route')} | {f.get('duration')} | {f.get('aircraft')}" 
                                for f in flights]
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

    @discord.ui.button(label="Edit Monday Flight 1", style=discord.ButtonStyle.secondary)
    async def edit_monday_flight1(self, interaction: discord.Interaction, button: Button):
        if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("Only staff can edit flights.", ephemeral=True)
            return
        if "monday" in self.routes and self.routes["monday"]["flights"]:
            modal = EditRouteModal(self, "monday", 0)
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message("No flight to edit!", ephemeral=True)

# More edit buttons can be dynamically generated based on flights count

class WeeklyRoutesDashboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.routes = load_routes()

    @app_commands.command(name="dashboard", description="View weekly routes dashboard")
    async def dashboard(self, interaction: discord.Interaction):
        if not any(role.id == STAFF_ROLE_ID for role in interaction.user.roles):
            await interaction.response.send_message("Only staff can access the dashboard.", ephemeral=True)
            return

        view = WeeklyRoutesDashboardView(self.routes)
        embed = discord.Embed(title="🗓️ Weekly Routes Dashboard", color=discord.Color.orange())
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            if day in self.routes:
                flights = self.routes[day].get("flights", [])
                flight_lines = [f"`{f.get('code')}` — {f.get('route')} | {f.get('duration')} | {f.get('aircraft')}" 
                                for f in flights]
                embed.add_field(name=day.title(), value="\n".join(flight_lines) if flight_lines else "No flights", inline=False)
            else:
                embed.add_field(name=day.title(), value="No flights", inline=False)

        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(WeeklyRoutesDashboard(bot))
