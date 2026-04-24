import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os

# Railway ENV Variable
IF_API_KEY = os.getenv("IF_API_KEY")

BASE_URL = "https://api.infiniteflight.com/public/v2"

SERVER_MAP = {
    "Casual": "casual",
    "Training": "training",
    "Expert": "expert"
}


class Aviation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # =========================
    # GET ACTIVE SESSION ID
    # =========================

    async def get_session_id(self, server_name: str):
        async with aiohttp.ClientSession() as session:
            url = f"{BASE_URL}/sessions?apikey={IF_API_KEY}"

            async with session.get(url) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                sessions = data.get("result", [])

                for s in sessions:
                    if server_name.lower() in s.get("name", "").lower():
                        return s.get("id")

        return None

    # =========================
    # /ATIS COMMAND
    # =========================

    @app_commands.command(
        name="atis",
        description="Get live ATIS + METAR + Airport Info"
    )
    @app_commands.describe(
        airport="Airport ICAO code (example: VOBL)"
    )
    async def atis(
        self,
        interaction: discord.Interaction,
        airport: str
    ):
        airport = airport.upper()

        class ServerSelect(discord.ui.Select):
            def __init__(self, cog):
                self.cog = cog

                options = [
                    discord.SelectOption(label="Casual", emoji="🟢"),
                    discord.SelectOption(label="Training", emoji="🟡"),
                    discord.SelectOption(label="Expert", emoji="🔴")
                ]

                super().__init__(
                    placeholder="Select Infinite Flight Server",
                    min_values=1,
                    max_values=1,
                    options=options,
                    custom_id="atis_server_select"
                )

            async def callback(self, select_interaction: discord.Interaction):
                await select_interaction.response.defer(ephemeral=True)

                selected = self.values[0]
                session_id = await self.cog.get_session_id(
                    SERVER_MAP[selected]
                )

                if not session_id:
                    return await select_interaction.followup.send(
                        f"❌ No active {selected} server found."
                    )

                async with aiohttp.ClientSession() as session:

                    # =========================
                    # ATIS
                    # =========================

                    atis_url = (
                        f"{BASE_URL}/sessions/"
                        f"{session_id}/airport/"
                        f"{airport}/atis?apikey={IF_API_KEY}"
                    )

                    async with session.get(atis_url) as resp:
                        if resp.status != 200:
                            return await select_interaction.followup.send(
                                "❌ Failed to fetch ATIS."
                            )

                        atis_data = await resp.json()

                    atis_result = atis_data.get("result")

                    if not atis_result:
                        atis_result = "No active ATIS available."

                    # =========================
                    # AIRPORT INFO
                    # =========================

                    airport_url = (
                        f"{BASE_URL}/airport/{airport}"
                        f"?apikey={IF_API_KEY}"
                    )

                    async with session.get(airport_url) as resp:
                        airport_name = "Unknown Airport"
                        country = "Unknown"

                        if resp.status == 200:
                            airport_data = await resp.json()
                            result = airport_data.get("result", {})

                            airport_name = result.get(
                                "name",
                                "Unknown Airport"
                            )

                            country = result.get(
                                "country",
                                "Unknown"
                            )

                # =========================
                # EMBED
                # =========================

                embed = discord.Embed(
                    title=f"📡 {airport} Aviation Information",
                    color=discord.Color.orange()
                )

                embed.add_field(
                    name="🛫 Airport",
                    value=f"**{airport_name}**\n{country}",
                    inline=False
                )

                embed.add_field(
                    name="🌐 Server",
                    value=selected,
                    inline=True
                )

                embed.add_field(
                    name="📍 ICAO",
                    value=airport,
                    inline=True
                )

                embed.add_field(
                    name="📻 Live ATIS",
                    value=f"```{atis_result}```",
                    inline=False
                )

                embed.add_field(
                    name="🌦 METAR",
                    value="(METAR system upgrade coming next)",
                    inline=False
                )

                embed.set_footer(
                    text="Akasa Air Virtual • Infinite Flight"
                )

                await select_interaction.followup.send(
                    embed=embed
                )

        class ServerView(discord.ui.View):
            def __init__(self, cog):
                super().__init__(timeout=None)
                self.add_item(ServerSelect(cog))

        await interaction.response.send_message(
            f"Select server for **{airport}**",
            view=ServerView(self),
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Aviation(bot))
