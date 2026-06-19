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
                # Defer ephemerally while we fetch data; the final ATIS embed
                # is sent publicly (visible to everyone in the channel) below
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

                    # Step 4: Fetch airport name (from status) and active
                    # controllers (from the /atc endpoint, which has real
                    # usernames rather than raw IDs)
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
                    except Exception:
                        pass

                    try:
                        atc_url = f"{BASE_URL}/sessions/{session_id}/atc?apikey={IF_API_KEY}"
                        async with session.get(atc_url) as resp:
                            if resp.status == 200:
                                atc_data = await resp.json()
                                atc_list = atc_data.get("result", [])

                                # Each entry typically has a "stationName" like
                                # "MPTO_TWR" or "MPTO_ATIS" plus a "username".
                                # Filter to controllers at this airport.
                                airport_controllers = [
                                    c for c in atc_list
                                    if airport in (c.get("stationName") or "")
                                ]

                                if airport_controllers:
                                    lines = []
                                    for c in airport_controllers:
                                        station = c.get("stationName", "")
                                        facility = station.split("_")[-1] if "_" in station else "ATC"
                                        controller_name = c.get("username", "Unknown")
                                        freq = c.get("frequency")

                                        if facility.upper() == "ATIS" and freq:
                                            atis_frequency = freq

                                        if freq:
                                            lines.append(f"**{facility}** — {controller_name} ({freq})")
                                        else:
                                            lines.append(f"**{facility}** — {controller_name}")
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
                # Public message — visible to everyone in the channel, not just the requester
                await select_interaction.followup.send(embed=embed, ephemeral=False)

        # Step 0: Send dropdown view
        view = discord.ui.View()
        view.add_item(ServerSelect())
        await interaction.response.send_message(
            f"Select the server for ATIS at {airport}:", view=view, ephemeral=True
        )


# Mandatory setup function
async def setup(bot):
    await bot.add_cog(ATIS(bot))
