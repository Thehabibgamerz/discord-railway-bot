import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Modal, TextInput, View, Button
from supabase import create_client, Client
import os

STAFF_ROLE_ID = 1389824693388837035
SUPABASE_URL = "https://xljanwcgesjhdoaavmuo.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


def get_db() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def is_staff(member: discord.Member) -> bool:
    return any(role.id == STAFF_ROLE_ID for role in member.roles)


# ================= SUPABASE HELPERS =================

def db_add_point(guild_id: int, user_id: int):
    db = get_db()
    try:
        res = db.table("airport_scores").select("*").eq("guild_id", guild_id).eq("user_id", user_id).single().execute()
        existing = res.data
        db.table("airport_scores").update({
            "points": existing["points"] + 1,
            "wins": existing["wins"] + 1
        }).eq("guild_id", guild_id).eq("user_id", user_id).execute()
    except Exception:
        db.table("airport_scores").insert({
            "guild_id": guild_id,
            "user_id": user_id,
            "points": 1,
            "wins": 1
        }).execute()


def db_get_leaderboard(guild_id: int):
    try:
        res = get_db().table("airport_scores").select("*").eq("guild_id", guild_id).order("points", desc=True).limit(10).execute()
        return res.data or []
    except Exception:
        return []


# ================= ACTIVE GAMES =================
# guild_id -> { icao, channel_id, message_id, solved }
active_games: dict = {}


# ================= GUESS MODAL =================

class GuessModal(Modal):
    def __init__(self, correct_icao: str, guild_id: int):
        super().__init__(title="Guess the Airport!")
        self.correct_icao = correct_icao.upper().strip()
        self.guild_id = guild_id

        self.guess = TextInput(
            label="Enter the ICAO code",
            placeholder="e.g. EGLL",
            max_length=4,
            min_length=3
        )
        self.add_item(self.guess)

    async def on_submit(self, interaction: discord.Interaction):
        game = active_games.get(self.guild_id)

        if not game or game.get("solved"):
            return await interaction.response.send_message(
                "⚠️ There is no active game right now.", ephemeral=True
            )

        submitted = self.guess.value.upper().strip()

        if submitted == self.correct_icao:
            # Mark solved immediately to prevent race conditions
            game["solved"] = True

            db_add_point(self.guild_id, interaction.user.id)

            embed = discord.Embed(
                title="✅ Correct!",
                description=(
                    f"🎉 {interaction.user.mention} guessed it right!\n\n"
                    f"**The airport was:** `{self.correct_icao}`\n\n"
                    f"+1 point added to your score!"
                ),
                color=discord.Color.green()
            )
            embed.set_footer(text="AkasaAirVirtual • Guess the Airport")

            # Disable the guess button on the original message
            channel = interaction.guild.get_channel(game["channel_id"])
            if channel and game.get("message_id"):
                try:
                    msg = await channel.fetch_message(game["message_id"])
                    disabled_view = View()
                    disabled_btn = Button(
                        label="Game Over",
                        emoji="🏁",
                        style=discord.ButtonStyle.secondary,
                        disabled=True
                    )
                    disabled_view.add_item(disabled_btn)
                    await msg.edit(view=disabled_view)
                except Exception:
                    pass

            await interaction.response.send_message(embed=embed)
            active_games.pop(self.guild_id, None)

        else:
            await interaction.response.send_message(
                f"❌ **{submitted}** is incorrect. Keep trying!",
                ephemeral=True
            )


# ================= GUESS BUTTON VIEW =================

class GuessView(View):
    def __init__(self, correct_icao: str, guild_id: int):
        super().__init__(timeout=None)
        self.correct_icao = correct_icao
        self.guild_id = guild_id

    @discord.ui.button(label="Submit Guess", emoji="🛬", style=discord.ButtonStyle.primary, custom_id="airport_guess_btn")
    async def submit_guess(self, interaction: discord.Interaction, button: Button):
        game = active_games.get(interaction.guild.id)
        if not game or game.get("solved"):
            return await interaction.response.send_message(
                "⚠️ There is no active game right now.", ephemeral=True
            )
        await interaction.response.send_modal(
            GuessModal(self.correct_icao, interaction.guild.id)
        )


# ================= COG =================

class GuessAirport(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="guessairport", description="Start a Guess the Airport game (staff only)")
    @app_commands.describe(
        icao="The correct ICAO code of the airport",
        hint="A clue or description for members",
        image="Screenshot of the airport from Infinite Flight"
    )
    async def guessairport(
        self,
        interaction: discord.Interaction,
        icao: str,
        hint: str,
        image: discord.Attachment
    ):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff can start a game.", ephemeral=True
            )

        if interaction.guild.id in active_games and not active_games[interaction.guild.id].get("solved"):
            return await interaction.response.send_message(
                "⚠️ A game is already active in this server. End it first with `/endguess`.",
                ephemeral=True
            )

        if not image.content_type or not image.content_type.startswith("image/"):
            return await interaction.response.send_message(
                "❌ Please attach a valid image file.", ephemeral=True
            )

        icao = icao.upper().strip()

        embed = discord.Embed(
            title="✈️ Guess the Airport!",
            description=(
                f"**Hint:** {hint}\n\n"
                "Click the button below to submit your guess.\n"
                "First one to get it right wins a point! 🏆"
            ),
            color=discord.Color.orange()
        )
        embed.set_image(url=image.url)
        embed.set_footer(text="AkasaAirVirtual • Guess the Airport")

        view = GuessView(icao, interaction.guild.id)

        await interaction.response.send_message("✅ Game started!", ephemeral=True)
        msg = await interaction.channel.send(embed=embed, view=view)

        active_games[interaction.guild.id] = {
            "icao": icao,
            "channel_id": interaction.channel.id,
            "message_id": msg.id,
            "solved": False
        }

    # ================= END GAME =================

    @app_commands.command(name="endguess", description="End the current airport guessing game (staff only)")
    async def endguess(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff can end a game.", ephemeral=True
            )

        game = active_games.pop(interaction.guild.id, None)

        if not game:
            return await interaction.response.send_message(
                "⚠️ No active game to end.", ephemeral=True
            )

        # Disable the guess button
        channel = interaction.guild.get_channel(game["channel_id"])
        if channel and game.get("message_id"):
            try:
                msg = await channel.fetch_message(game["message_id"])
                disabled_view = View()
                disabled_btn = Button(
                    label="Game Over",
                    emoji="🏁",
                    style=discord.ButtonStyle.secondary,
                    disabled=True
                )
                disabled_view.add_item(disabled_btn)
                await msg.edit(view=disabled_view)
            except Exception:
                pass

        await interaction.response.send_message(
            f"🏁 Game ended. The answer was **`{game['icao']}`**."
        )

    # ================= LEADERBOARD =================

    @app_commands.command(name="airportleaderboard", description="Show the Guess the Airport leaderboard")
    async def airportleaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()

        rows = db_get_leaderboard(interaction.guild.id)

        if not rows:
            return await interaction.followup.send(
                "⚠️ No scores yet — start a game with `/guessairport`!"
            )

        embed = discord.Embed(
            title="🏆 Guess the Airport — Leaderboard",
            color=discord.Color.orange()
        )

        medals = ["🥇", "🥈", "🥉"]
        lines = []

        for i, row in enumerate(rows):
            member = interaction.guild.get_member(row["user_id"])
            name = member.display_name if member else f"<@{row['user_id']}>"
            medal = medals[i] if i < 3 else f"**#{i + 1}**"
            lines.append(f"{medal} {name} — **{row['points']}** point{'s' if row['points'] != 1 else ''}")

        embed.description = "\n".join(lines)
        embed.set_footer(text="AkasaAirVirtual • Guess the Airport")

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(GuessAirport(bot))
