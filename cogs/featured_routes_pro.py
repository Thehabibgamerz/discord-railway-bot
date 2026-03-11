import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")

# Storage (can later upgrade to JSON/database)
weekly_routes = {
    "Monday": [],
    "Tuesday": [],
    "Wednesday": [],
    "Thursday": [],
    "Friday": [],
    "Saturday": [],
    "Sunday": []
}

multiplier = "2x"

class FeaturedRoutes(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.route_channel = None
        self.auto_post.start()

    # Auto post every midnight IST
    @tasks.loop(minutes=1)
    async def auto_post(self):

        now = datetime.datetime.now(IST)

        if now.hour == 0 and now.minute == 0 and self.route_channel:

            today = now.strftime("%A")

            routes = weekly_routes.get(today, [])

            embed = discord.Embed(
                title=f"🗺️ Featured Routes — {today}",
                description=(
                    f"All pilots are eligible to fly the following featured routes.\n"
                    f"These flights offer a **{multiplier} multiplier**, making it a great opportunity to maximize your rewards.\n\n"
                    f"Ensure compliance with airline procedures and standard operating practices."
                ),
                color=discord.Color.orange()
            )

            if routes:
                embed.add_field(
                    name="Routes",
                    value="\n".join(routes),
                    inline=False
                )
            else:
                embed.add_field(
                    name="Routes",
                    value="No routes scheduled.",
                    inline=False
                )

            await self.route_channel.send(embed=embed)

    # Set channel
    @app_commands.command(name="setrouteschannel", description="Set the featured routes posting channel")
    async def setrouteschannel(self, interaction: discord.Interaction, channel: discord.TextChannel):

        self.route_channel = channel

        await interaction.response.send_message(
            f"✅ Featured routes will now post in {channel.mention}", ephemeral=True
        )

    # Add route
    @app_commands.command(name="addroute", description="Add a route to a specific day")
    async def addroute(self, interaction: discord.Interaction, day: str, route: str):

        day = day.capitalize()

        if day not in weekly_routes:
            await interaction.response.send_message("❌ Invalid day.", ephemeral=True)
            return

        weekly_routes[day].append(route)

        await interaction.response.send_message(
            f"✅ Route added to **{day}**", ephemeral=True
        )

    # Remove route
    @app_commands.command(name="removeroute", description="Remove a route from a day")
    async def removeroute(self, interaction: discord.Interaction, day: str, index: int):

        day = day.capitalize()

        try:
            weekly_routes[day].pop(index-1)
            await interaction.response.send_message("🗑️ Route removed.", ephemeral=True)
        except:
            await interaction.response.send_message("❌ Invalid route index.", ephemeral=True)

    # Set multiplier
    @app_commands.command(name="setmultiplier", description="Change route multiplier")
    async def setmultiplier(self, interaction: discord.Interaction, value: str):

        global multiplier
        multiplier = value

        await interaction.response.send_message(
            f"⭐ Multiplier updated to **{value}**", ephemeral=True
        )

    # Preview weekly routes
    @app_commands.command(name="weeklyroutes", description="Preview weekly featured routes")
    async def weeklyroutes(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="🗺️ Weekly Featured Routes Schedule",
            color=discord.Color.orange()
        )

        for day, routes in weekly_routes.items():

            if routes:
                value = "\n".join(routes)
            else:
                value = "No routes scheduled."

            embed.add_field(
                name=day,
                value=value,
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    # Dashboard command
    @app_commands.command(name="routesdashboard", description="View and manage featured routes")
    async def routesdashboard(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="⚙️ Featured Routes Dashboard",
            description=(
                "Use the following commands to manage routes:\n\n"
                "`/addroute` — Add route\n"
                "`/removeroute` — Remove route\n"
                "`/setmultiplier` — Change multiplier\n"
                "`/weeklyroutes` — View schedule\n"
                "`/setrouteschannel` — Set posting channel"
            ),
            color=discord.Color.orange()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(FeaturedRoutes(bot))
