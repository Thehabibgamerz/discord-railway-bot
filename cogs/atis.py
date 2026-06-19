import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os

# Use environment variable for security on Railway
IF_API_KEY = os.getenv("IF_API_KEY")
BASE_URL = "https://api.infiniteflight.com/public/v2"

SERVER_MAP = {
    "Casual": "casual",
    "Training": "training",
    "Expert": "expert"
}


class ATISServerSelect(discord.ui.Select):
    def __init__(self, airport: str):
        self.airport = airport

        options = [
            discord.SelectOption(label="Casual", description="Casual Server"),
            discord.SelectOption(label="Training", description="Training Server"),
            discord.SelectOption(label="Expert", description="Expert Server")
        ]

        super().__init__(placeholder="Select a server...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        # Defer ephemerally while we fetch data; the final result is public below
        await interaction.response.defer(ephemeral=True, thinking=True)

        server_choice = self.values[0]
        server_key = SERVER_MAP[server_choice]
        airport = self.airport

        # Step 1: Find the active session for this server
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{BASE_URL}/sessions?apikey={IF_API_KEY}") as resp:
                    if resp.status == 401:
                        await interaction.followup.send(
                            "❌ Invalid API key! Please check your Infinite Flight API key.", ephemeral=True
                        )
                        return
                    elif resp.status != 200:
                        await interaction.followup.send(
                            f"⚠️ Failed to fetch sessions (HTTP {resp.status})", ephemeral=True
                        )
                        return
                    sessions_data = await resp.json()
            except Exception as e:
                await interaction.followup.send(f"❌ Error fetching sessions: {e}", ephemeral=True)
                return

        sessions = sessions_data.get("result", [])
        session_id = None
        for s in sessions:
            if server_key.lower() in s.get("name", "").lower():
                session_id = s.get("id")
                break

        if not session_id:
            await interaction.followup.send(
                f"⚠️ No active {server_choice} session found.", ephemeral=True
            )
            return

        async with aiohttp.ClientSession() as session:

            # Step 2: Fetch ATIS text
            atis_url = f"{BASE_URL}/sessions/{session_id}/airport/{airport}/atis?apikey={IF_API_KEY}"
            try:
                async with session.get(atis_url) as resp:
                    if resp.status == 401:
                        await interaction.followup.send(
                            "❌ Invalid API key! Cannot fetch ATIS.", ephemeral=True
                        )
                        return
                    elif resp.status != 200:
                        await interaction.followup.send(
                            f"⚠️ Failed to fetch ATIS (HTTP {resp.status})", ephemeral=True
                        )
                        return
                    atis_data = await resp.json()
            except Exception as e:
                await interaction.followup.send(f"❌ Error fetching ATIS: {e}", ephemeral=True)
                return

            error_code = atis_data.get("errorCode")
            result_text = atis_data.get("result")

            if error_code != 0 or not result_text:
                await interaction.followup.send(
                    "No ATIS available for this airport.", ephemeral=False
                )
                return

            # Step 3: Fetch METAR / weather
            metar_text = "Unavailable"
            try:
                weather_url = f"{BASE_URL}/sessions/{session_id}/weather/{airport}?apikey={IF_API_KEY}"
                async with session.get(weather_url) as resp:
                    if resp.status == 200:
                        weather_data = await resp.json()
                        w_result = weather_data.get("result", {})
                        metar_text = (
                            w_result.get("metar")
                            or w_result.get("raw")
                            or "Unavailable"
                        )
            except Exception:
                pass

        # Step 4: Build embed — ATIS + METAR only
        embed = discord.Embed(
            title=f"📡 {airport} ATIS",
            description=f"```{result_text}```",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="🌦️ METAR",
            value=f"```{metar_text}```",
            inline=False
        )

        embed.set_footer(text=f"AkasaAirVirtual • Infinite Flight Live • {server_choice} Server")

        # Public message — visible to everyone in the channel, not just the requester
        await interaction.followup.send(embed=embed, ephemeral=False)


class ATISServerSelectView(discord.ui.View):
    def __init__(self, airport: str):
        super().__init__(timeout=120)
        self.add_item(ATISServerSelect(airport))


class ATIS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="atis", description="Get live ATIS info for an airport on Infinite Flight")
    @app_commands.describe(airport="Airport ICAO code")
    async def atis(self, interaction: discord.Interaction, airport: str):
        airport = airport.upper()

        await interaction.response.send_message(
            f"Select the server for ATIS at **{airport}**:",
            view=ATISServerSelectView(airport),
            ephemeral=True
        )


# Mandatory setup function
async def setup(bot):
    await bot.add_cog(ATIS(bot))
