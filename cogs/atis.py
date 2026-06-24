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

SERVER_COLORS = {
    "Casual": discord.Color.green(),
    "Training": discord.Color.blue(),
    "Expert": discord.Color.orange()
}


class ATISServerSelect(discord.ui.Select):
    def __init__(self, airport: str):
        self.airport = airport

        options = [
            discord.SelectOption(label="Casual", description="Casual Server", emoji="🟢"),
            discord.SelectOption(label="Training", description="Training Server", emoji="🔵"),
            discord.SelectOption(label="Expert", description="Expert Server", emoji="🟠")
        ]

        super().__init__(placeholder="✈️ Select a server...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        server_choice = self.values[0]
        server_key = SERVER_MAP[server_choice]
        airport = self.airport

        # Step 1: Find session
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"{BASE_URL}/sessions?apikey={IF_API_KEY}") as resp:
                    if resp.status == 401:
                        return await interaction.followup.send("❌ Invalid API key.", ephemeral=True)
                    elif resp.status != 200:
                        return await interaction.followup.send(
                            f"⚠️ Failed to fetch sessions (HTTP {resp.status})", ephemeral=True
                        )
                    sessions_data = await resp.json()
            except Exception as e:
                return await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

        sessions = sessions_data.get("result", [])
        session_id = None
        for s in sessions:
            if server_key.lower() in s.get("name", "").lower():
                session_id = s.get("id")
                break

        if not session_id:
            return await interaction.followup.send(
                f"⚠️ No active {server_choice} session found.", ephemeral=True
            )

        async with aiohttp.ClientSession() as session:

            # Step 2: Fetch ATIS
            try:
                async with session.get(
                    f"{BASE_URL}/sessions/{session_id}/airport/{airport}/atis?apikey={IF_API_KEY}"
                ) as resp:
                    if resp.status == 401:
                        return await interaction.followup.send("❌ Invalid API key.", ephemeral=True)
                    elif resp.status != 200:
                        return await interaction.followup.send(
                            f"⚠️ Failed to fetch ATIS (HTTP {resp.status})", ephemeral=True
                        )
                    atis_data = await resp.json()
            except Exception as e:
                return await interaction.followup.send(f"❌ Error fetching ATIS: {e}", ephemeral=True)

            error_code = atis_data.get("errorCode")
            result_text = atis_data.get("result")

            if error_code != 0 or not result_text:
                return await interaction.followup.send(
                    f"❌ No active ATIS available for **{airport}** on the {server_choice} server.",
                    ephemeral=False
                )

            # Step 3: Fetch METAR
            metar_text = None
            try:
                async with session.get(
                    f"{BASE_URL}/sessions/{session_id}/weather/{airport}?apikey={IF_API_KEY}"
                ) as resp:
                    if resp.status == 200:
                        weather_data = await resp.json()
                        w = weather_data.get("result", {})
                        metar_text = w.get("metar") or w.get("raw")
            except Exception:
                pass

        # Step 4: Build embed
        embed = discord.Embed(
            title=f"📡 ATIS — {airport}",
            color=SERVER_COLORS.get(server_choice, discord.Color.orange())
        )

        embed.add_field(
            name="🖥️ Server",
            value=server_choice,
            inline=True
        )

        embed.add_field(
            name="🛫 Airport",
            value=airport,
            inline=True
        )

        embed.add_field(
            name="\u200b",
            value="\u200b",
            inline=True
        )

        embed.add_field(
            name="📢 ATIS Information",
            value=f"```{result_text}```",
            inline=False
        )

        embed.add_field(
            name="🌦️ METAR",
            value=f"```{metar_text}```" if metar_text else "```Unavailable```",
            inline=False
        )

        embed.set_footer(
            text=f"AkasaAirVirtual • Infinite Flight Live • {server_choice} Server"
        )

        # Public — visible to the whole channel
        await interaction.followup.send(embed=embed, ephemeral=False)


class ATISServerSelectView(discord.ui.View):
    def __init__(self, airport: str):
        super().__init__(timeout=120)
        self.add_item(ATISServerSelect(airport))


class ATIS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="atis", description="Get live ATIS info for an airport on Infinite Flight")
    @app_commands.describe(airport="Airport ICAO code (e.g. EGLL, OMDB, VIDP)")
    async def atis(self, interaction: discord.Interaction, airport: str):
        airport = airport.upper().strip()

        await interaction.response.send_message(
            f"✈️ Select the server to fetch ATIS for **{airport}**:",
            view=ATISServerSelectView(airport),
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(ATIS(bot))
