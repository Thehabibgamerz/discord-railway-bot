import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Modal, TextInput, View, Button
from supabase import create_client, Client
from datetime import datetime, timezone
import os

STAFF_ROLE_ID = 1389824693388837035
SUPABASE_URL = "https://xljanwcgesjhdoaavmuo.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

MULTIPLIER_VALUES = ["1.5x", "1.3x", "1.1x"]  # 1st, 2nd, 3rd place


def get_db() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def is_staff(member: discord.Member) -> bool:
    return any(role.id == STAFF_ROLE_ID for role in member.roles)


# ================= SUPABASE HELPERS =================

def db_create_game(guild_id: int, channel_id: int, message_id: int, icao: str) -> int:
    res = get_db().table("airport_games").insert({
        "guild_id": guild_id,
        "channel_id": channel_id,
        "message_id": message_id,
        "icao": icao.upper(),
        "active": True
    }).execute()
    return res.data[0]["id"]


def db_get_active_game(guild_id: int):
    try:
        res = get_db().table("airport_games").select("*").eq("guild_id", guild_id).eq("active", True).single().execute()
        return res.data
    except Exception:
        return None


def db_close_game(game_id: int):
    get_db().table("airport_games").update({"active": False}).eq("id", game_id).execute()


def db_has_answered(game_id: int, user_id: int) -> bool:
    try:
        res = get_db().table("airport_answers").select("id").eq("game_id", game_id).eq("user_id", user_id).single().execute()
        return res.data is not None
    except Exception:
        return False


def db_submit_answer(game_id: int, user_id: int, answer: str):
    get_db().table("airport_answers").insert({
        "game_id": game_id,
        "user_id": user_id,
        "answer": answer.upper().strip(),
        "submitted_at": datetime.now(timezone.utc).isoformat()
    }).execute()


def db_get_answers(game_id: int):
    try:
        res = get_db().table("airport_answers").select("*").eq("game_id", game_id).order("submitted_at", desc=False).execute()
        return res.data or []
    except Exception:
        return []


def db_add_multiplier(guild_id: int, user_id: int, multiplier: str):
    db = get_db()
    try:
        db.table("airport_multipliers").insert({
            "guild_id": guild_id,
            "user_id": user_id,
            "multiplier": multiplier,
            "used": False
        }).execute()
    except Exception:
        pass


def db_get_multiplier(guild_id: int, user_id: int):
    try:
        res = get_db().table("airport_multipliers").select("*").eq("guild_id", guild_id).eq("user_id", user_id).eq("used", False).order("created_at", desc=True).limit(1).single().execute()
        return res.data
    except Exception:
        return None


def db_use_multiplier(multiplier_id: int):
    get_db().table("airport_multipliers").update({"used": True}).eq("id", multiplier_id).execute()


def db_get_leaderboard(guild_id: int):
    try:
        res = get_db().table("airport_scores").select("*").eq("guild_id", guild_id).order("points", desc=True).limit(10).execute()
        return res.data or []
    except Exception:
        return []


def db_add_point(guild_id: int, user_id: int):
    db = get_db()
    try:
        res = db.table("airport_scores").select("*").eq("guild_id", guild_id).eq("user_id", user_id).single().execute()
        existing = res.data
        db.table("airport_scores").update({
            "points": existing["points"] + 1
        }).eq("guild_id", guild_id).eq("user_id", user_id).execute()
    except Exception:
        db.table("airport_scores").insert({
            "guild_id": guild_id,
            "user_id": user_id,
            "points": 1
        }).execute()


# ================= ANSWER MODAL =================

class AnswerModal(Modal):
    def __init__(self, game_id: int, guild_id: int):
        super().__init__(title="Guess the Airport!")
        self.game_id = game_id
        self.guild_id = guild_id

        self.guess = TextInput(
            label="Enter the ICAO code",
            placeholder="e.g. EGLL",
            max_length=4,
            min_length=3
        )
        self.add_item(self.guess)

    async def on_submit(self, interaction: discord.Interaction):
        # Re-check game is still active
        game = db_get_active_game(self.guild_id)
        if not game:
            return await interaction.response.send_message(
                "⚠️ There is no active game right now.", ephemeral=True
            )

        # Prevent double submission
        if db_has_answered(self.game_id, interaction.user.id):
            return await interaction.response.send_message(
                "⚠️ You have already submitted an answer for this game!", ephemeral=True
            )

        db_submit_answer(self.game_id, interaction.user.id, self.guess.value)

        await interaction.response.send_message(
            f"✅ Your answer **{self.guess.value.upper().strip()}** has been recorded! "
            f"Wait for the staff to reveal the answer. ✈️",
            ephemeral=True
        )


# ================= REVEAL VIEW =================

class RevealView(View):
    def __init__(self, game_id: int, guild_id: int):
        super().__init__(timeout=None)
        self.game_id = game_id
        self.guild_id = guild_id
        self.submit_btn.custom_id = f"airport_submit:{game_id}"
        self.reveal_btn.custom_id = f"airport_reveal:{game_id}"

    @discord.ui.button(label="Submit Answer", emoji="🛬", style=discord.ButtonStyle.primary)
    async def submit_btn(self, interaction: discord.Interaction, button: Button):
        game = db_get_active_game(interaction.guild.id)
        if not game:
            return await interaction.response.send_message(
                "⚠️ This game has already ended.", ephemeral=True
            )

        if db_has_answered(game["id"], interaction.user.id):
            return await interaction.response.send_message(
                "⚠️ You have already submitted an answer!", ephemeral=True
            )

        await interaction.response.send_modal(AnswerModal(game["id"], interaction.guild.id))

    @discord.ui.button(label="Answer Reveal", emoji="🔍", style=discord.ButtonStyle.danger)
    async def reveal_btn(self, interaction: discord.Interaction, button: Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff can reveal the answer.", ephemeral=True
            )

        game = db_get_active_game(interaction.guild.id)
        if not game:
            return await interaction.response.send_message(
                "⚠️ No active game to reveal.", ephemeral=True
            )

        await interaction.response.defer()

        correct_icao = game["icao"]
        answers = db_get_answers(game["id"])

        # Close the game
        db_close_game(game["id"])

        # Disable buttons on the original message
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        # Separate correct and incorrect
        correct_answers = [a for a in answers if a["answer"] == correct_icao]
        incorrect_answers = [a for a in answers if a["answer"] != correct_icao]

        # Award points and multipliers to first 3 correct
        multiplier_winners = []
        for i, ans in enumerate(correct_answers[:3]):
            db_add_point(interaction.guild.id, ans["user_id"])
            multiplier = MULTIPLIER_VALUES[i]
            db_add_multiplier(interaction.guild.id, ans["user_id"], multiplier)
            multiplier_winners.append((ans["user_id"], multiplier))

        # Also award points to remaining correct answers (no multiplier)
        for ans in correct_answers[3:]:
            db_add_point(interaction.guild.id, ans["user_id"])

        # Build reveal embed
        embed = discord.Embed(
            title="🔍 Answer Reveal!",
            description=f"The correct airport was:\n# ✈️ `{correct_icao}`",
            color=discord.Color.orange()
        )

        # Participants list in submission order
        if answers:
            participant_lines = []
            position = 1
            for ans in answers:
                member = interaction.guild.get_member(ans["user_id"])
                name = member.mention if member else f"<@{ans['user_id']}>"
                is_correct = ans["answer"] == correct_icao
                status = "✅" if is_correct else "❌"

                # Find if they have a multiplier reward
                mult_text = ""
                for uid, mult in multiplier_winners:
                    if uid == ans["user_id"]:
                        medals = ["🥇", "🥈", "🥉"]
                        mult_text = f" {medals[multiplier_winners.index((uid, mult))]} **{mult} multiplier!**"
                        break

                participant_lines.append(
                    f"`#{position}` {status} {name} — `{ans['answer']}`{mult_text}"
                )
                position += 1

            embed.add_field(
                name=f"📋 Participants ({len(answers)})",
                value="\n".join(participant_lines) if participant_lines else "No submissions.",
                inline=False
            )
        else:
            embed.add_field(
                name="📋 Participants",
                value="Nobody submitted an answer.",
                inline=False
            )

        # Summary
        embed.add_field(
            name="📊 Summary",
            value=(
                f"✅ Correct: **{len(correct_answers)}**\n"
                f"❌ Incorrect: **{len(incorrect_answers)}**\n"
                f"👥 Total: **{len(answers)}**"
            ),
            inline=False
        )

        if multiplier_winners:
            mult_lines = []
            medals = ["🥇", "🥈", "🥉"]
            for i, (uid, mult) in enumerate(multiplier_winners):
                member = interaction.guild.get_member(uid)
                name = member.mention if member else f"<@{uid}>"
                mult_lines.append(f"{medals[i]} {name} — **{mult}** on next flight!")
            embed.add_field(
                name="🎯 Flight Multipliers Awarded",
                value="\n".join(mult_lines),
                inline=False
            )

        embed.set_footer(text="AkasaAirVirtual • Guess the Airport")

        await interaction.followup.send(embed=embed)


# ================= COG =================

class GuessAirport(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="guessairport", description="Start a Guess the Airport game (staff only)")
    @app_commands.describe(
        icao="The correct ICAO code of the airport",
        image="Screenshot of the airport from Infinite Flight"
    )
    async def guessairport(
        self,
        interaction: discord.Interaction,
        icao: str,
        image: discord.Attachment
    ):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff can start a game.", ephemeral=True
            )

        existing = db_get_active_game(interaction.guild.id)
        if existing:
            return await interaction.response.send_message(
                "⚠️ A game is already active! Reveal the answer first.", ephemeral=True
            )

        if not image.content_type or not image.content_type.startswith("image/"):
            return await interaction.response.send_message(
                "❌ Please attach a valid image file.", ephemeral=True
            )

        icao = icao.upper().strip()

        embed = discord.Embed(
            title="✈️ Guess the Airport!",
            description=(
                "Can you identify this airport?\n\n"
                "Click **Submit Answer** and enter the ICAO code.\n"
                "Staff will reveal the answer when ready. 🏆"
            ),
            color=discord.Color.orange()
        )
        embed.set_image(url=image.url)
        embed.set_footer(text="AkasaAirVirtual • Guess the Airport")

        # Temp view to get message ID first
        await interaction.response.send_message("✅ Posting game...", ephemeral=True)
        msg = await interaction.channel.send(embed=embed)

        # Create game in DB
        game_id = db_create_game(interaction.guild.id, interaction.channel.id, msg.id, icao)

        # Now attach the real view with the game_id
        view = RevealView(game_id, interaction.guild.id)
        await msg.edit(view=view)

    # ================= MY MULTIPLIER =================

    @app_commands.command(name="mymultiplier", description="Check if you have an active flight multiplier")
    async def mymultiplier(self, interaction: discord.Interaction):
        row = db_get_multiplier(interaction.guild.id, interaction.user.id)

        if not row:
            return await interaction.response.send_message(
                "⚠️ You don't have an active multiplier right now.", ephemeral=True
            )

        embed = discord.Embed(
            title="🎯 Your Flight Multiplier",
            description=(
                f"You have an active multiplier of **{row['multiplier']}** "
                f"for your next flight!\n\n"
                "Contact staff to apply it to your PIREP."
            ),
            color=discord.Color.orange()
        )
        embed.set_footer(text="AkasaAirVirtual • Guess the Airport Reward")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ================= USE MULTIPLIER (staff) =================

    @app_commands.command(name="usemultiplier", description="Mark a member's multiplier as used (staff only)")
    @app_commands.describe(member="The member whose multiplier to mark as used")
    async def usemultiplier(self, interaction: discord.Interaction, member: discord.Member):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Staff only.", ephemeral=True)

        row = db_get_multiplier(interaction.guild.id, member.id)

        if not row:
            return await interaction.response.send_message(
                f"⚠️ {member.mention} has no active multiplier.", ephemeral=True
            )

        db_use_multiplier(row["id"])

        await interaction.response.send_message(
            f"✅ {member.mention}'s **{row['multiplier']}** multiplier has been marked as used.",
            ephemeral=True
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
            pts = row["points"]
            lines.append(f"{medal} {name} — **{pts}** correct guess{'es' if pts != 1 else ''}")

        embed.description = "\n".join(lines)
        embed.set_footer(text="AkasaAirVirtual • Guess the Airport")

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(GuessAirport(bot))
