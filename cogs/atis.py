import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os

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
    # ATIS COMMAND
    # =========================

    @app_commands.command(
        name="atis",
        description="Get live ATIS for an airport"
    )
    async def atis(
        self,
        interaction: discord.Interaction,
        airport: str
    ):

        airport = airport.upper()

        class ServerSelect(discord.ui.Select):

            def __init__(self):

                options = [
                    discord.SelectOption(label="Casual", emoji="🟢"),
                    discord.SelectOption(label="Training", emoji="🟡"),
                    discord.SelectOption(label="Expert", emoji="🔴")
                ]

                super().__init__(
                    placeholder="Select a server...",
                    min_values=1,
                    max_values=1,
                    options=options
                )

            async def callback(self, select_interaction: discord.Interaction):

                await select_interaction.response.defer()

                server_choice = self.values[0]
                server_key = SERVER_MAP[server_choice]

                headers = {
                    "Authorization": f"Bearer {IF_API_KEY}"
                }

                try:

                    async with aiohttp.ClientSession() as session:

                        # GET SESSIONS
                        async with session.get(
                            f"{BASE_URL}/sessions",
                            headers=headers
                        ) as resp:

                            sessions_data = await resp.json()

                        sessions = sessions_data.get("result", [])

                        session_id = None

                        for s in sessions:

                            if server_key.lower() in s["name"].lower():
                                session_id = s["id"]
                                break

                        if not session_id:
                            return await select_interaction.followup.send(
                                "❌ Session not found"
                            )

                        # GET ATIS
                        async with session.get(
                            f"{BASE_URL}/sessions/{session_id}/airport/{airport}/atis",
                            headers=headers
                        ) as resp:

                            atis_data = await resp.json()

                        if atis_data.get("errorCode") != 0:
                            return await select_interaction.followup.send(
                                f"❌ No active ATIS for {airport}"
                            )

                        atis_text = atis_data.get(
                            "result",
                            "No ATIS available"
                        )

                        embed = discord.Embed(
                            title=f"📡 ATIS • {airport}",
                            description=f"```{atis_text}```",
                            color=discord.Color.orange()
                        )

                        embed.add_field(
                            name="🌐 Server",
                            value=server_choice
                        )

                        embed.set_footer(
                            text="Akasa Air Virtual"
                        )

                        await select_interaction.followup.send(
                            embed=embed
                        )

                except Exception as e:

                    await select_interaction.followup.send(
                        f"❌ Error:\n```{e}```"
                    )

        class ServerView(discord.ui.View):

            def __init__(self):
                super().__init__(timeout=120)
                self.add_item(ServerSelect())

        await interaction.response.send_message(
            f"Select server for `{airport}`",
            view=ServerView(),
            ephemeral=True
        )

    # =========================
    # METAR COMMAND
    # =========================

    @app_commands.command(
        name="metar",
        description="Get METAR weather for an airport"
    )
    async def metar(
        self,
        interaction: discord.Interaction,
        airport: str
    ):

        airport = airport.upper()

        url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{airport}.TXT"

        try:

            async with aiohttp.ClientSession() as session:

                async with session.get(url) as resp:

                    if resp.status != 200:
                        return await interaction.response.send_message(
                            f"❌ METAR not found for {airport}"
                        )

                    text = await resp.text()

            lines = text.splitlines()

            if len(lines) < 2:
                return await interaction.response.send_message(
                    "❌ Invalid METAR data"
                )

            observation_time = lines[0]
            metar_raw = lines[1]

            embed = discord.Embed(
                title=f"🌦️ METAR • {airport}",
                color=discord.Color.blue()
            )

            embed.add_field(
                name="🕒 Observation",
                value=observation_time,
                inline=False
            )

            embed.add_field(
                name="📡 Raw METAR",
                value=f"```{metar_raw}```",
                inline=False
            )

            embed.set_footer(
                text="NOAA Aviation Weather"
            )

            await interaction.response.send_message(
                embed=embed
            )

        except Exception as e:

            await interaction.response.send_message(
                f"❌ Error:\n```{e}```"
            )


async def setup(bot):
    await bot.add_cog(Aviation(bot))
