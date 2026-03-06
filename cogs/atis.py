import discord
from discord.ext import commands
from discord import app_commands
import aiohttp

IF_API_KEY = "tephscpkg4qe7xxkrfwvo9qrteksdj0l"
BASE_URL = "https://api.infiniteflight.com/public/v2/sessions/{sessionId}/airport/{airportIcao}/atis?apikey=tephscpkg4qe7xxkrfwvo9qrteksdj0l"

# Map friendly server names to API session names
SERVER_MAP = {
    "Casual": "casual",
    "Training": "training",
    "Expert": "expert"
}

class ATIS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Dropdown server selection
    @app_commands.command(name="atis", description="Get live ATIS info for an airport on Infinite Flight")
    @app_commands.describe(
        airport="Airport ICAO code"
    )
    async def atis(self, interaction: discord.Interaction, airport: str):
        airport = airport.upper()

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
                server_api_name = SERVER_MAP[server_choice]

                # Fetch ATIS
                async with aiohttp.ClientSession() as session:
                    url = f"{BASE_URL}/{server_api_name}/airport/{airport}/atis?apikey={IF_API_KEY}"
                    try:
                        async with session.get(url) as resp:
                            if resp.status != 200:
                                await select_interaction.response.send_message(
                                    f"❌ Failed to fetch ATIS (HTTP {resp.status})", ephemeral=True
                                )
                                return
                            data = await resp.json()
                    except Exception as e:
                        await select_interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
                        return

                result_text = data.get("result")
                error_code = data.get("errorCode")
                if error_code != 0 or not result_text:
                    await select_interaction.response.send_message(
                        f"⚠️ No active ATIS available for {airport} on {server_choice}.", ephemeral=True
                    )
                    return

                embed = discord.Embed(
                    title=f"ATIS for {airport} — {server_choice}",
                    description=f"📡 {result_text}",
                    color=discord.Color.green()
                )
                embed.set_footer(text="Data provided by Infinite Flight Live API")
                await select_interaction.response.send_message(embed=embed)

        view = discord.ui.View()
        view.add_item(ServerSelect())
        await interaction.response.send_message(f"Select the server for ATIS at {airport}:", view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(ATIS(bot))
