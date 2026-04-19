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
                server_choice = self.values[0]
                server_key = SERVER_MAP[server_choice]

                # Step 1: Fetch active sessions
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(f"{BASE_URL}/sessions?apikey={IF_API_KEY}") as resp:
                            if resp.status == 401:
                                await select_interaction.response.send_message(
                                    "❌ Invalid API key! Please check your Infinite Flight API key.", ephemeral=True
                                )
                                return
                            elif resp.status != 200:
                                await select_interaction.response.send_message(
                                    f"⚠️ Failed to fetch sessions (HTTP {resp.status})", ephemeral=True
                                )
                                return
                            sessions_data = await resp.json()
                    except Exception as e:
                        await select_interaction.response.send_message(f"❌ Error fetching sessions: {e}", ephemeral=True)
                        return

                # Step 2: Find session ID
                sessions = sessions_data.get("result", [])
                session_id = None
                for s in sessions:
                    if server_key.lower() in s.get("name", "").lower():
                        session_id = s.get("id")
                        break

                if not session_id:
                    await select_interaction.response.send_message(
                        f"⚠️ No active {server_choice} session found.", ephemeral=True
                    )
                    return

                # Step 3: Fetch ATIS
                async with aiohttp.ClientSession() as session:
                    url = f"{BASE_URL}/sessions/{session_id}/airport/{airport}/atis?apikey={IF_API_KEY}"
                    try:
                        async with session.get(url) as resp:
                            if resp.status == 401:
                                await select_interaction.response.send_message(
                                    "❌ Invalid API key! Cannot fetch ATIS.", ephemeral=True
                                )
                                return
                            elif resp.status != 200:
                                await select_interaction.response.send_message(
                                    f"⚠️ Failed to fetch ATIS (HTTP {resp.status})", ephemeral=True
                                )
                                return
                            atis_data = await resp.json()
                    except Exception as e:
                        await select_interaction.response.send_message(f"❌ Error fetching ATIS: {e}", ephemeral=True)
                        return

                error_code = atis_data.get("errorCode")
                result_text = atis_data.get("result")

                if error_code != 0 or not result_text:
                    await select_interaction.response.send_message(
                        f"⚠️ No active ATIS available for {airport} on {server_choice}.", ephemeral=True
                    )
                    return

                # Step 4: Send embed
                embed = discord.Embed(
                    title=f"ATIS for {airport} — {server_choice}",
                    description=f"📡 `{result_text}`",
                    color=discord.Color.orange()
                )
                embed.set_footer(text="AkasaAirVirtual")
                await select_interaction.response.send_message(embed=embed)

        # Step 0: Send dropdown view
        view = discord.ui.View()
        view.add_item(ServerSelect())
        await interaction.response.send_message(
            f"Select the server for ATIS at {airport}:", view=view, ephemeral=True
        )


# Mandatory setup function
async def setup(bot):
    await bot.add_cog(ATIS(bot))
