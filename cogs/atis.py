import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os
from datetime import datetime, timezone

# Use environment variable for security on Railway
IF_API_KEY = os.getenv("IF_API_KEY")
BASE_URL = "https://api.infiniteflight.com/public/v2"

SERVER_MAP = {
    "Casual": "casual",
    "Training": "training",
    "Expert": "expert"
}

# ATC facility type IDs used by the Infinite Flight Live API.
# Adjust these if they don't match what comes back in your testing.
ATC_FACILITY_TYPES = {
    0: "Ground",
    1: "Tower",
    2: "Unicom",
    3: "Clearance",
    4: "Approach",
    5: "Departure",
    6: "Center",
    7: "ATIS"
}


class ATIS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="atis", description="Get live ATIS info for an airport on Infinite Flight")
    @app_commands.describe(airport="Airport ICAO code")
    async def atis(self, interaction: discord.Interaction, airport: str):
        airport = airport.upper()

        # Dropdown for server selection
        class ServerSelect(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label="Casual", description="Casual Server"),
                    discord.SelectOption(label="Training", description="Training Server"),
                    discord.SelectOption(label="Expert", description="Expert Server")
                ]
                super().__init__(placeholder="Select a server...", min_values=1, max_values=1, options=options)

            async def callback(self, select_interaction: discord.Interaction):
                # Defer since we're making several API calls
                await select_interaction.response.defer(ephemeral=True, thinking=True)

                server_choice = self.values[0]
                server_key = SERVER_MAP[server_choice]

                # Step 1: Fetch active sessions
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(f"{BASE_URL}/sessions?apikey={IF_API_KEY}") as resp:
                            if resp.status == 401:
                                await select_interaction.followup.send(
                                    "❌ Invalid API key! Please check your Infinite Flight API key.", ephemeral=True
                                )
                                return
                            elif resp.status != 200:
                                await select_interaction.followup.send(
                                    f"⚠️ Failed to fetch sessions (HTTP {resp.status})", ephemeral=True
                                )
                                return
                            sessions_data = await resp.json()
                    except Exception as e:
                        await select_interaction.followup.send(f"❌ Error fetching sessions: {e}", ephemeral=True)
                        return

                # Step 2: Find session ID
                sessions = sessions_data.get("result", [])
                session_id = None
                for s in sessions:
                    if server_key.lower() in s.get("name", "").lower():
                        session_id = s.get("id")
                        break

                if not session_id:
                    await select_interaction.followup.send(
                        f"⚠️ No active {server_choice} session found.", ephemeral=True
                    )
                    return

                async with aiohttp.ClientSession() as session:

                    # Step 3: Fetch ATIS text
                    atis_url = f"{BASE_URL}/sessions/{session_id}/airport/{airport}/atis?apikey={IF_API_KEY}"
                    try:
                        async with session.get(atis_url) as resp:
                            if resp.status == 401:
                                await select_interaction.followup.send(
                                    "❌ Invalid API key! Cannot fetch ATIS.", ephemeral=True
                                )
                                return
                            elif resp.status != 200:
                                await select_interaction.followup.send(
                                    f"⚠️ Failed to fetch ATIS (HTTP {resp.status})", ephemeral=True
                                )
                                return
                            atis_data = await resp.json()
                    except Exception as e:
                        await select_interaction.followup.send(f"❌ Error fetching ATIS: {e}", ephemeral=True)
                        return

                    error_code = atis_data.get("errorCode")
                    result_text = atis_data.get("result")

                    if error_code != 0 or not result_text:
                        await select_interaction.followup.send(
                            f"⚠️ No active ATIS available for {airport} on {server_choice}.", ephemeral=True
                        )
                        return

                    # Step 4: Fetch airport status (name + active controllers/frequencies)
                    airport_name = airport
                    controllers_text = "None online"
                    atis_frequency = None

                    try:
                        status_url = f"{BASE_URL}/sessions/{session_id}/airport/{airport}/status?apikey={IF_API_KEY}"
                        async with session.get(status_url) as resp:
                            if resp.status == 200:
                                status_data = await resp.json()
                                result = status_data.get("result", {})

                                airport_name = result.get("airportName") or airport

                                facilities = result.get("atcFacilities", [])
                                if facilities:
                                    lines = []
                                    for f in facilities:
                                        f_type = ATC_FACILITY_TYPES.get(f.get("type"), f.get("type"))
                                        freq = f.get("frequency") or f.get("frequencyId") or "N/A"
                                        lines.append(f"**{f_type}** — {freq}")
                                        if f_type == "ATIS":
                                            atis_frequency = freq
                                    controllers_text = "\n".join(lines)
                    except Exception:
                        # Non-fatal — just fall back to defaults above
                        pass

                    # Step 5: Fetch METAR / weather
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

                # Step 6: Build embed
                embed = discord.Embed(
                    title=f"📡 ATIS — {airport_name} ({airport})",
                    description=f"```{result_text}```",
                    color=discord.Color.orange()
                )

                embed.add_field(
                    name="🖥️ Server",
                    value=server_choice,
                    inline=True
                )

                embed.add_field(
                    name="📻 ATIS Frequency",
                    value=atis_frequency or "N/A",
                    inline=True
                )

                embed.add_field(
                    name="🕐 Updated",
                    value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:R>",
                    inline=True
                )

                embed.add_field(
                    name="🎙️ Active Controllers",
                    value=controllers_text,
                    inline=False
                )

                embed.add_field(
                    name="🌦️ METAR",
                    value=f"```{metar_text}```",
                    inline=False
                )

                embed.set_footer(text="AkasaAirVirtual • Infinite Flight Live")
                await select_interaction.followup.send(embed=embed)

        # Step 0: Send dropdown view
        view = discord.ui.View()
        view.add_item(ServerSelect())
        await interaction.response.send_message(
            f"Select the server for ATIS at {airport}:", view=view, ephemeral=True
        )


# Mandatory setup function
async def setup(bot):
    await bot.add_cog(ATIS(bot))
