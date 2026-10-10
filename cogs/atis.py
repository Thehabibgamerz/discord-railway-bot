
import os
import re
import asyncio
import aiohttp
import discord

from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone


IF_API_KEY = os.getenv("IF_API_KEY")
BASE_URL = "https://api.infiniteflight.com/public/v2"

EXPERT_COLOR = discord.Color.orange()
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)


async def fetch_atis(airport: str):
    """Fetch live ATIS and weather from the Infinite Flight Expert Server."""

    if not IF_API_KEY:
        return None, "❌ The IF_API_KEY environment variable is missing."

    try:
        async with aiohttp.ClientSession(
            timeout=REQUEST_TIMEOUT
        ) as session:

            # 1. Find the Expert Server session
            async with session.get(
                f"{BASE_URL}/sessions",
                params={"apikey": IF_API_KEY}
            ) as response:

                if response.status == 401:
                    return None, "❌ Invalid Infinite Flight API key."

                if response.status != 200:
                    return None, (
                        f"⚠️ Failed to fetch sessions "
                        f"(HTTP {response.status})."
                    )

                sessions_data = await response.json(
                    content_type=None
                )

            if sessions_data.get("errorCode", 0) != 0:
                return None, "❌ Infinite Flight API returned an error."

            sessions = sessions_data.get("result", [])

            # Match Expert Server, not Casual or Training.
            expert_session = next(
                (
                    server for server in sessions
                    if "expert" in server.get("name", "").lower()
                ),
                None
            )

            if not expert_session:
                return None, (
                    "⚠️ No active Infinite Flight Expert Server "
                    "session was found."
                )

            session_id = expert_session.get("id")

            if not session_id:
                return None, "❌ The Expert Server session ID is missing."

            # 2. Fetch ATIS
            async with session.get(
                f"{BASE_URL}/sessions/{session_id}/airport/"
                f"{airport}/atis",
                params={"apikey": IF_API_KEY}
            ) as response:

                if response.status == 401:
                    return None, "❌ Invalid Infinite Flight API key."

                if response.status != 200:
                    return None, (
                        f"⚠️ Failed to fetch ATIS "
                        f"(HTTP {response.status})."
                    )

                atis_data = await response.json(
                    content_type=None
                )

            if atis_data.get("errorCode") != 0:
                return None, (
                    f"❌ No ATIS is currently available for "
                    f"**{airport}** on the Expert Server."
                )

            atis_text = atis_data.get("result")

            if isinstance(atis_text, dict):
                atis_text = (
                    atis_text.get("atis")
                    or atis_text.get("text")
                    or str(atis_text)
                )

            if not isinstance(atis_text, str) or not atis_text.strip():
                return None, (
                    f"❌ No ATIS information is currently available "
                    f"for **{airport}** on the Expert Server."
                )

            # 3. Fetch weather / METAR
            metar_text = None

            try:
                async with session.get(
                    f"{BASE_URL}/sessions/{session_id}/weather/"
                    f"{airport}",
                    params={"apikey": IF_API_KEY}
                ) as response:

                    if response.status == 200:
                        weather_data = await response.json(
                            content_type=None
                        )
                        weather = weather_data.get("result", {})

                        if isinstance(weather, dict):
                            metar_text = (
                                weather.get("metar")
                                or weather.get("raw")
                                or weather.get("rawMetar")
                                or weather.get("rawMETAR")
                                or weather.get("observation")
                            )

                        elif isinstance(weather, str):
                            metar_text = weather

            except (aiohttp.ClientError, asyncio.TimeoutError):
                # ATIS can still be displayed if weather is unavailable.
                pass

            return {
                "airport": airport,
                "atis": atis_text,
                "metar": metar_text,
                "server": expert_session.get(
                    "name", "Expert Server"
                ),
                "updated": discord.utils.utcnow()
            }, None

    except asyncio.TimeoutError:
        return None, (
            "⏱️ Infinite Flight API timed out. Please try again."
        )

    except aiohttp.ClientError:
        return None, (
            "🌐 Could not connect to the Infinite Flight API. "
            "Please try again later."
        )

    except (ValueError, TypeError, AttributeError):
        return None, (
            "⚠️ Received an unexpected response from the "
            "Infinite Flight API."
        )


def make_atis_embed(data: dict) -> discord.Embed:
    """Build the ATIS embed."""

    airport = data["airport"]
    atis_text = data["atis"]
    metar_text = data["metar"]

    embed = discord.Embed(
        title=f"📡 Airport ATIS — {airport}",
        description=(
            "Live airport information from the "
            "**Infinite Flight Expert Server**."
        ),
        color=EXPERT_COLOR,
        timestamp=data["updated"]
    )

    embed.add_field(
        name="🛫 Airport ICAO",
        value=f"`{airport}`",
        inline=True
    )

    embed.add_field(
        name="🖥️ Server",
        value="🟠 Expert",
        inline=True
    )

    embed.add_field(
        name="🕒 Updated",
        value=discord.utils.format_dt(
            data["updated"], style="R"
        ),
        inline=True
    )

    # Keep embed fields within Discord's character limits.
    atis_text = atis_text.strip()
    if len(atis_text) > 4000:
        atis_text = atis_text[:3997] + "..."

    embed.add_field(
        name="📢 ATIS Information",
        value=f"```text\n{atis_text}\n```",
        inline=False
    )

    if metar_text:
        metar_text = str(metar_text).strip()
        if len(metar_text) > 1000:
            metar_text = metar_text[:997] + "..."

        metar_value = f"```text\n{metar_text}\n```"
    else:
        metar_value = (
            "Weather information is currently unavailable."
        )

    embed.add_field(
        name="🌦️ METAR / Weather",
        value=metar_value,
        inline=False
    )

    embed.set_footer(
        text="Akasa Air Virtual • Infinite Flight Live"
    )

    return embed


class ATISRefreshView(discord.ui.View):
    def __init__(self, airport: str):
        super().__init__(timeout=900)
        self.airport = airport

    @discord.ui.button(
        label="Refresh ATIS",
        emoji="🔄",
        style=discord.ButtonStyle.primary
    )
    async def refresh(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.defer()

        data, error = await fetch_atis(self.airport)

        if error:
            return await interaction.followup.send(
                error,
                ephemeral=True
            )

        embed = make_atis_embed(data)

        # Update the existing public ATIS message.
        await interaction.message.edit(
            embed=embed,
            view=self
        )

        await interaction.followup.send(
            f"✅ ATIS for **{self.airport}** refreshed.",
            ephemeral=True
        )


class ATIS(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="atis",
        description="Get live airport ATIS from the Infinite Flight Expert Server"
    )
    @app_commands.describe(
        airport="Four-letter ICAO airport code, e.g. VIDP, VABB or EGLL"
    )
    @app_commands.guild_only()
    async def atis(
        self,
        interaction: discord.Interaction,
        airport: str
    ):
        airport = airport.strip().upper()

        # Basic ICAO format validation.
        if not re.fullmatch(r"[A-Z]{4}", airport):
            return await interaction.response.send_message(
                "❌ Enter a valid four-letter ICAO code, "
                "for example `VIDP`, `VABB`, or `EGLL`.",
                ephemeral=True
            )

        await interaction.response.defer(
            ephemeral=True,
            thinking=True
        )

        data, error = await fetch_atis(airport)

        if error:
            return await interaction.followup.send(
                error,
                ephemeral=True
            )

        embed = make_atis_embed(data)
        view = ATISRefreshView(airport)

        # Publish the ATIS in the channel.
        try:
            await interaction.channel.send(
                embed=embed,
                view=view
            )
        except (discord.Forbidden, discord.HTTPException):
            return await interaction.followup.send(
                "❌ I couldn't post the ATIS. Please check my "
                "channel permissions and try again.",
                ephemeral=True
            )

        await interaction.followup.send(
            f"✅ ATIS for **{airport}** posted from the "
            "**Expert Server**.",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(ATIS(bot))
