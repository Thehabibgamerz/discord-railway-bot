import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")

STAFF_ROLE = 1389824693388837035
ROUTE_CHANNEL = 1389839700642238516

# Storage (simple memory storage)
weekly_routes = {
    "Monday": [],
    "Tuesday": [],
    "Wednesday": [],
    "Thursday": [],
    "Friday": [],
    "Saturday": [],
    "Sunday": []
}

multipliers = {
    "Monday": "1x",
    "Tuesday": "1x",
    "Wednesday": "1x",
    "Thursday": "1x",
    "Friday": "2x",
    "Saturday": "2x",
    "Sunday": "2x"
}


class Routes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auto_post.start()

    # ----------------------------
    # Set route channel
    # ----------------------------

    @app_commands.command(name="setroutechannel", description="Set the featured routes channel")
    async def setroutechannel(self, interaction: discord.Interaction, channel: discord.TextChannel):

        if STAFF_ROLE not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message("❌ Staff only.", ephemeral=True)
            return

        global ROUTE_CHANNEL
        ROUTE_CHANNEL = channel.id

        await interaction.response.send_message(f"✅ Routes channel set to {channel.mention}")

    # ----------------------------
    # Set routes
    # ----------------------------

    @app_commands.command(name="setroutes", description="Set routes for a specific day")
    async def setroutes(
        self,
        interaction: discord.Interaction,
        day: str,
        multiplier: str,
        route1: str,
        route2: str,
        route3: str
    ):

        if STAFF_ROLE not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message("❌ Staff only.", ephemeral=True)
            return

        day = day.capitalize()

        weekly_routes[day] = [route1, route2, route3]
        multipliers[day] = multiplier

        await interaction.response.send_message(f"✅ Routes updated for **{day}**")

    # ----------------------------
    # Weekly preview
    # ----------------------------

    @app_commands.command(name="weeklyroutes", description="Preview weekly featured routes")
    async def weeklyroutes(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="🗺️ Weekly Featured Routes",
            color=discord.Color.orange()
        )

        for day, routes in weekly_routes.items():

            if not routes:
                routes_text = "No routes set"
            else:
                routes_text = "\n".join(routes)

            embed.add_field(
                name=f"{day} • Multiplier {multipliers[day]}",
                value=routes_text,
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    # ----------------------------
    # Post today's routes
    # ----------------------------

    async def post_today_routes(self, channel):

        today = datetime.now(IST).strftime("%A")
        routes = weekly_routes.get(today, [])

        if not routes:
            return

        embed = discord.Embed(
            title=f"🗺️ Featured Routes — {today}",
            description=(
                "All pilots are eligible to fly the following featured routes.\n"
                f"These flights offer a **{multipliers[today]} multiplier**, "
                "making it a great opportunity to maximize your rewards.\n\n"
                "Ensure compliance with airline procedures and standard operating practices."
            ),
            color=discord.Color.orange()
        )

        embed.add_field(
            name="Routes",
            value="\n".join(routes),
            inline=False
        )

        embed.set_footer(text="Akasa Air Virtual • Happy Flying ✈️")

        await channel.send(embed=embed)

    # ----------------------------
    # Manual post
    # ----------------------------

    @app_commands.command(name="postroutes", description="Post today's featured routes")
    async def postroutes(self, interaction: discord.Interaction):

        if STAFF_ROLE not in [r.id for r in interaction.user.roles]:
            await interaction.response.send_message("❌ Staff only.", ephemeral=True)
            return

        if ROUTE_CHANNEL is None:
            await interaction.response.send_message("⚠️ Routes channel not set.", ephemeral=True)
            return

        channel = interaction.guild.get_channel(ROUTE_CHANNEL)

        await self.post_today_routes(channel)

        await interaction.response.send_message("✅ Routes posted.")

    # ----------------------------
    # Auto post daily at midnight IST
    # ----------------------------

    @tasks.loop(minutes=1)
    async def auto_post(self):

        now = datetime.now(IST)

        if now.hour == 0 and now.minute == 0:

            if ROUTE_CHANNEL is None:
                return

            channel = self.bot.get_channel(ROUTE_CHANNEL)

            if channel:
                await self.post_today_routes(channel)


async def setup(bot):
    await bot.add_cog(Routes(bot))
