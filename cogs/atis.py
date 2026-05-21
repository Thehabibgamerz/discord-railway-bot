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
        description="Get live airport info"
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
                    placeholder="Select server...",
                    options=options
                )

            async def callback(self, select_interaction: discord.Interaction):

                await select_interaction.response.defer()

                headers = {
                    "Authorization": f"Bearer {IF_API_KEY}"
                }

                server_choice = self.values[0]
                server_key = SERVER_MAP[server_choice]

                try:

                    async with aiohttp.ClientSession() as session:

                        # ================= GET SESSIONS =================

                        async with session.get(
                            f"{BASE_URL}/sessions",
                            headers=headers
                        ) as resp:

                            data = await resp.json()

                        sessions = data.get("result", [])

                        session_id = None

                        for s in sessions:

                            if server_key.lower() in s["name"].lower():
                                session_id = s["id"]
                                break

                        if not session_id:
                            return await select_interaction.followup.send(
                                "❌ Session not found"
                            )

                        # ================= WORLD DATA =================

                        async with session.get(
                            f"{BASE_URL}/sessions/{session_id}/world",
                            headers=headers
                        ) as resp:

                            world_data = await resp.json()

                        result = world_data.get("result", {})

                        airports = result.get("airports", [])

                        airport_data = None

                        for a in airports:

                            if a.get("icao", "").upper() == airport:
                                airport_data = a
                                break

                        if not airport_data:
                            return await select_interaction.followup.send(
                                f"❌ Airport `{airport}` not found on {server_choice}"
                            )

                        inbound = airport_data.get(
                            "inboundFlightsCount",
                            0
                        )

                        outbound = airport_data.get(
                            "outboundFlightsCount",
                            0
                        )

                        frequencies = airport_data.get(
                            "frequencies",
                            []
                        )

                        # ================= FREQUENCIES =================

                        freq_text = ""

                        if frequencies:

                            for freq in frequencies:

                                freq_name = freq.get(
                                    "type",
                                    "Unknown"
                                )

                                freq_value = freq.get(
                                    "frequency",
                                    "Unknown"
                                )

                                freq_text += (
                                    f"• {freq_name}: {freq_value}\n"
                                )

                        else:
                            freq_text = "No active ATC"

                        # ================= CONTROLLERS =================

                        controllers = []

                        for freq in frequencies:

                            username = freq.get("username")

                            if username:
                                controllers.append(
                                    f"• {username}"
                                )

                        controllers_text = (
                            "\n".join(controllers)
                            if controllers
                            else "No active controllers"
                        )

                        # ================= ATIS =================

                        atis_text = "No active ATIS"

                        async with session.get(
                            f"{BASE_URL}/sessions/{session_id}/airport/{airport}/atis",
                            headers=headers
                        ) as resp:

                            if resp.status == 200:

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
                            f"{freq_text}\n"

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

        class ServerView(discord.ui.View):

            def __init__(self):
                super().__init__(timeout=120)
                self.add_item(ServerSelect())

        await interaction.response.send_message(
            f"Select a server for `{airport}`",
            view=ServerView(),
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(ATIS(bot))
