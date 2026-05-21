import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import os

# ================= CONFIG =================

IF_API_KEY = os.getenv("IF_API_KEY")

BASE_URL = "https://api.infiniteflight.com/public/v2"

SERVER_MAP = {
    "Casual": "casual",
    "Training": "training",
    "Expert": "expert"
}

# ================= COG =================

class ATIS(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # ================= COMMAND =================

    @app_commands.command(
        name="atis",
        description="Get live airport information from Infinite Flight"
    )
    @app_commands.describe(
        airport="Airport ICAO code"
    )
    async def atis(
        self,
        interaction: discord.Interaction,
        airport: str
    ):

        airport = airport.upper()

        # ================= SERVER SELECT =================

        class ServerSelect(discord.ui.Select):

            def __init__(self):

                options = [
                    discord.SelectOption(
                        label="Casual",
                        emoji="🟢",
                        description="Casual Server"
                    ),
                    discord.SelectOption(
                        label="Training",
                        emoji="🟡",
                        description="Training Server"
                    ),
                    discord.SelectOption(
                        label="Expert",
                        emoji="🔴",
                        description="Expert Server"
                    )
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

                        # ================= GET SESSIONS =================

                        async with session.get(
                            f"{BASE_URL}/sessions",
                            headers=headers
                        ) as resp:

                            if resp.status != 200:
                                return await select_interaction.followup.send(
                                    f"❌ Failed to fetch sessions ({resp.status})"
                                )

                            if resp.content_type != "application/json":
                                text = await resp.text()
                                return await select_interaction.followup.send(
                                    f"❌ Invalid API response\n```{text[:1000]}```"
                                )

                            sessions_data = await resp.json()

                        # ================= FIND SESSION =================

                        session_id = None

                        for s in sessions_data.get("result", []):

                            if server_key.lower() in s.get("name", "").lower():
                                session_id = s.get("id")
                                break

                        if not session_id:
                            return await select_interaction.followup.send(
                                "❌ Server session not found."
                            )

                        # ================= AIRPORT DATA =================

                        airport_url = (
                            f"{BASE_URL}/sessions/"
                            f"{session_id}/airport/{airport}"
                        )

                        async with session.get(
                            airport_url,
                            headers=headers
                        ) as resp:

                            if resp.status != 200:
                                return await select_interaction.followup.send(
                                    f"❌ Failed to fetch airport info ({resp.status})"
                                )

                            if resp.content_type != "application/json":
                                text = await resp.text()
                                return await select_interaction.followup.send(
                                    f"❌ Invalid airport response\n```{text[:1000]}```"
                                )

                            airport_data = await resp.json()

                        result = airport_data.get("result", {})

                        # ================= FLIGHTS =================

                        inbound = result.get("inboundFlightsCount", "Unknown")
                        outbound = result.get("outboundFlightsCount", "Unknown")

                        # ================= FREQUENCIES =================

                        frequencies = result.get("frequencies", [])

                        freq_text = ""

                        if frequencies:

                            for freq in frequencies:

                                freq_name = freq.get("type", "Unknown")
                                freq_value = freq.get("frequency", "Unknown")

                                freq_text += (
                                    f"• {freq_name}: {freq_value}\n"
                                )

                        else:
                            freq_text = "No active ATC"

                        # ================= CONTROLLERS =================

                        controllers_text = ""

                        if frequencies:

                            controller_lines = []

                            for freq in frequencies:

                                controller = freq.get("username")

                                if controller:
                                    controller_lines.append(
                                        f"• {controller}"
                                    )

                            if controller_lines:
                                controllers_text = "\n".join(controller_lines)
                            else:
                                controllers_text = "No active controllers"

                        else:
                            controllers_text = "No active controllers"

                        # ================= ATIS =================

                        atis_url = (
                            f"{BASE_URL}/sessions/"
                            f"{session_id}/airport/{airport}/atis"
                        )

                        async with session.get(
                            atis_url,
                            headers=headers
                        ) as resp:

                            atis_text = "No active ATIS"

                            if resp.status == 200:

                                if resp.content_type == "application/json":

                                    atis_data = await resp.json()

                                    if atis_data.get("errorCode") == 0:
                                        atis_text = atis_data.get(
                                            "result",
                                            "No active ATIS"
                                        )

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
                            f"{freq_text}\n\n"

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

                except Exception as e:

                    await select_interaction.followup.send(
                        f"❌ API Error:\n```{e}```"
                    )

        # ================= VIEW =================

        class ServerView(discord.ui.View):

            def __init__(self):
                super().__init__(timeout=120)
                self.add_item(ServerSelect())

        # ================= SEND =================

        await interaction.response.send_message(
            f"Select a server for `{airport}`",
            view=ServerView(),
            ephemeral=True
        )


# ================= SETUP =================

async def setup(bot):
    await bot.add_cog(ATIS(bot))
