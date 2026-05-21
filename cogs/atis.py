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


class ATIS(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="atis",
        description="Get airport ATIS + ATC information"
    )
    async def atis(
        self,
        interaction: discord.Interaction,
        airport: str
    ):

        airport = airport.upper()

        # ================= DROPDOWN =================

        class ServerSelect(discord.ui.Select):

            def __init__(self):

                options = [
                    discord.SelectOption(
                        label="Casual",
                        emoji="🟢"
                    ),
                    discord.SelectOption(
                        label="Training",
                        emoji="🟡"
                    ),
                    discord.SelectOption(
                        label="Expert",
                        emoji="🔴"
                    )
                ]

                super().__init__(
                    placeholder="Select Infinite Flight Server",
                    min_values=1,
                    max_values=1,
                    options=options
                )

            async def callback(self, select_interaction: discord.Interaction):

                await select_interaction.response.defer()

                server_choice = self.values[0]
                server_key = SERVER_MAP[server_choice]

                # ================= FETCH SESSION =================

                async with aiohttp.ClientSession() as session:

                    try:
                        async with session.get(
                            f"{BASE_URL}/sessions/{IF_API_KEY}"
                        ) as resp:

                            data = await resp.json()

                    except Exception as e:
                        return await select_interaction.followup.send(
                            f"❌ API Error:\n```{e}```"
                        )

                sessions = data.get("result", [])

                session_id = None

                for s in sessions:

                    if server_key.lower() in s["name"].lower():
                        session_id = s["id"]
                        break

                if not session_id:
                    return await select_interaction.followup.send(
                        "❌ Server not found."
                    )

                # ================= FETCH ATIS =================

                async with aiohttp.ClientSession() as session:

                    atis_url = (
                        f"{BASE_URL}/sessions/"
                        f"{session_id}/airport/"
                        f"{airport}/atis?apikey={IF_API_KEY}"
                    )

                    status_url = (
                        f"{BASE_URL}/sessions/"
                        f"{session_id}/airport/"
                        f"{airport}/status?apikey={IF_API_KEY}"
                    )

                    atc_url = (
                        f"{BASE_URL}/sessions/"
                        f"{session_id}/airport/"
                        f"{airport}/atc?apikey={IF_API_KEY}"
                    )

                    try:

                        async with session.get(atis_url) as r1:
                            atis_data = await r1.json()

                        async with session.get(status_url) as r2:
                            status_data = await r2.json()

                        async with session.get(atc_url) as r3:
                            atc_data = await r3.json()

                    except Exception as e:
                        return await select_interaction.followup.send(
                            f"❌ Failed fetching airport data:\n```{e}```"
                        )

                # ================= ATIS =================

                atis_text = atis_data.get("result")

                if not atis_text:
                    atis_text = "No active ATIS"

                # ================= STATUS =================

                status = status_data.get("result", {})

                inbound = status.get("inboundFlightsCount", "Unknown")
                outbound = status.get("outboundFlightsCount", "Unknown")

                # ================= ATC =================

                atc_result = atc_data.get("result", [])

                frequencies = []
                controllers = []

                if atc_result:

                    for freq in atc_result:

                        facility = freq.get("type", "Unknown")
                        frequency = freq.get("frequency", "Unknown")

                        frequencies.append(
                            f"• {facility} ({frequency})"
                        )

                        controller = freq.get("username")

                        if controller:
                            controllers.append(
                                f"• {controller}"
                            )

                if not frequencies:
                    frequencies_text = "No active ATC"
                else:
                    frequencies_text = "\n".join(frequencies)

                if not controllers:
                    controllers_text = "No active controllers"
                else:
                    controllers_text = "\n".join(controllers)

                # ================= EMBED =================

                embed = discord.Embed(
                    title=f"📡 {airport} Airport Information",
                    color=discord.Color.orange()
                )

                embed.description = (
                    f"🌐 **Server:** {server_choice}\n"
                    f"🛬 **Inbound Flights:** {inbound}\n"
                    f"🛫 **Outbound Flights:** {outbound}\n\n"

                    f"🎧 **Active Frequencies**\n"
                    f"{frequencies_text}\n\n"

                    f"👨‍✈️ **Active Controllers**\n"
                    f"{controllers_text}\n\n"

                    f"📡 **Live ATIS**\n"
                    f"```{atis_text}```"
                )

                embed.set_footer(
                    text="Akasa Air Virtual • Infinite Flight"
                )

                await select_interaction.followup.send(
                    embed=embed
                )

        # ================= VIEW =================

        view = discord.ui.View(timeout=60)
        view.add_item(ServerSelect())

        await interaction.response.send_message(
            f"Select a server for `{airport}`",
            view=view,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(ATIS(bot))
