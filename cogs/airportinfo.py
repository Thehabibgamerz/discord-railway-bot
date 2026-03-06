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

class AirportInfoPro(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="airportinfo", description="Get info about an airport including live ATIS")
    @app_commands.describe(icao="Airport ICAO code (e.g., VOBL, KJFK)")
    async def airportinfo(self, interaction: discord.Interaction, icao: str):
        icao = icao.upper()

        # Dropdown for server selection
        class ServerSelect(discord.ui.Select):
            def __init__(self):
                options = [
                    discord.SelectOption(label="Casual", description="Casual Server"),
                    discord.SelectOption(label="Training", description="Training Server"),
                    discord.SelectOption(label="Expert", description="Expert Server")
                ]
                super().__init__(placeholder="Select server...", min_values=1, max_values=1, options=options)

            async def callback(self, select_interaction: discord.Interaction):
                server_choice = self.values[0]
                server_key = SERVER_MAP[server_choice]

                # Step 1: Fetch airport info
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{BASE_URL}/airports/{icao}?apikey={IF_API_KEY}") as resp:
                        if resp.status != 200:
                            await select_interaction.response.send_message(
                                f"❌ Failed to fetch info for {icao} (HTTP {resp.status})",
                                ephemeral=True
                            )
                            return
                        airport_data = await resp.json()

                if not airport_data.get("result"):
                    await select_interaction.response.send_message(
                        f"⚠️ No data found for {icao}", ephemeral=True
                    )
                    return

                info = airport_data["result"]
                # Runways
                runways = info.get("runways", [])
                runway_list = "\n".join([f"{r['ident1']}/{r['ident2']} — {r['length']}m | {r['surface']}" for r in runways]) or "No runway data"
                # Gates
                gates = info.get("gates", [])
                gate_list = ", ".join([g['name'] for g in gates]) or "No gates data"
                # Elevation
                elevation = info.get("elevation", "N/A")

                # Step 2: Fetch active sessions for ATIS
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{BASE_URL}/sessions?apikey={IF_API_KEY}") as resp:
                        if resp.status != 200:
                            await select_interaction.response.send_message(
                                f"⚠️ Failed to fetch sessions (HTTP {resp.status})", ephemeral=True
                            )
                            return
                        sessions_data = await resp.json()

                sessions = sessions_data.get("result", [])
                session_id = None
                for s in sessions:
                    if server_key.lower() in s.get("name", "").lower():
                        session_id = s.get("id")
                        break

                atis_text = None
                if session_id:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{BASE_URL}/sessions/{session_id}/airport/{icao}/atis?apikey={IF_API_KEY}") as resp:
                            if resp.status == 200:
                                atis_data = await resp.json()
                                atis_text = atis_data.get("result")

                # Embed message
                embed = discord.Embed(
                    title=f"🛫 Airport Info — {icao} ({server_choice})",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Elevation", value=f"{elevation} ft", inline=True)
                embed.add_field(name="Runways", value=runway_list, inline=False)
                embed.add_field(name="Gates", value=gate_list, inline=False)
                if atis_text:
                    embed.add_field(name="ATIS", value=f"📡 {atis_text}", inline=False)
                embed.set_footer(text="Data provided by Infinite Flight Live API")

                await select_interaction.response.send_message(embed=embed)

        view = discord.ui.View()
        view.add_item(ServerSelect())
        await interaction.response.send_message(
            f"Select the server for {icao} airport info:", view=view, ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(AirportInfoPro(bot))
