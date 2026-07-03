import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
from supabase import create_client, Client
import os
import random

STAFF_ROLE_ID = 1389824693388837035
SUPABASE_URL = "https://xljanwcgesjhdoaavmuo.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

MIN_NUMBER = 1
MAX_NUMBER = 100


def get_db() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def is_staff(member: discord.Member) -> bool:
    return any(role.id == STAFF_ROLE_ID for role in member.roles)


# ================= SUPABASE HELPERS =================

def db_update_score(guild_id: int, user_id: int, streak: int):
    db = get_db()
    try:
        res = db.table("hl_scores").select("*").eq("guild_id", guild_id).eq("user_id", user_id).single().execute()
        existing = res.data
        new_best = max(existing["best_streak"], streak)
        db.table("hl_scores").update({
            "total_wins": existing["total_wins"] + 1,
            "best_streak": new_best
        }).eq("guild_id", guild_id).eq("user_id", user_id).execute()
    except Exception:
        db.table("hl_scores").insert({
            "guild_id": guild_id,
            "user_id": user_id,
            "total_wins": 1,
            "best_streak": streak
        }).execute()


def db_get_leaderboard(guild_id: int):
    try:
        res = get_db().table("hl_scores").select("*").eq("guild_id", guild_id).order("best_streak", desc=True).limit(10).execute()
        return res.data or []
    except Exception:
        return []


# ================= ACTIVE GAMES =================
# guild_id -> { number, current_low, current_high, streak, last_user_id, message_id, channel_id }
active_games: dict = {}


# ================= GAME VIEW =================

def build_embed(game: dict, result_text: str = None, color=None) -> discord.Embed:
    embed = discord.Embed(
        title="🔢 Higher or Lower",
        color=color or discord.Color.orange()
    )
    embed.add_field(
        name="🎯 Current Number",
        value=f"# **{game['current_number']}**",
        inline=False
    )
    embed.add_field(
        name="📊 Range",
        value=f"`{game['current_low']}` — `{game['current_high']}`",
        inline=True
    )
    embed.add_field(
        name="🔥 Streak",
        value=f"**{game['streak']}** correct",
        inline=True
    )
    if result_text:
        embed.add_field(name="\u200b", value=result_text, inline=False)
    embed.set_footer(text="AkasaAirVirtual • Higher or Lower")
    return embed


class HLView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=120)
        self.guild_id = guild_id

    async def handle_guess(self, interaction: discord.Interaction, guess: str):
        game = active_games.get(self.guild_id)

        if not game:
            return await interaction.response.send_message(
                "⚠️ No active game. Start one with `/higherorlower`.", ephemeral=True
            )

        secret = game["secret"]
        current = game["current_number"]
        correct = (guess == "higher" and secret > current) or (guess == "lower" and secret < current)

        if correct:
            game["streak"] += 1
            game["last_user_id"] = interaction.user.id
            game["current_number"] = secret

            # Narrow the range
            if guess == "higher":
                game["current_low"] = current + 1
            else:
                game["current_high"] = current - 1

            # Pick next secret
            if game["current_low"] >= game["current_high"]:
                # Range exhausted — player wins
                db_update_score(self.guild_id, interaction.user.id, game["streak"])
                active_games.pop(self.guild_id, None)

                embed = build_embed(game, color=discord.Color.gold())
                embed.add_field(
                    name="🏆 You Win!",
                    value=(
                        f"{interaction.user.mention} won with a streak of **{game['streak']}**!\n"
                        f"The number was **{secret}** — no more numbers left in the range!"
                    ),
                    inline=False
                )

                for child in self.children:
                    child.disabled = True

                return await interaction.response.edit_message(embed=embed, view=self)

            game["secret"] = random.randint(game["current_low"], game["current_high"])

            result = f"✅ **Correct!** {interaction.user.mention} — streak: **{game['streak']}**"
            embed = build_embed(game, result_text=result, color=discord.Color.green())
            await interaction.response.edit_message(embed=embed, view=self)

        else:
            # Wrong guess — game over
            streak = game["streak"]
            active_games.pop(self.guild_id, None)

            for child in self.children:
                child.disabled = True

            embed = discord.Embed(
                title="❌ Game Over!",
                description=(
                    f"{interaction.user.mention} guessed **{guess.upper()}** but the number was **{secret}**!\n\n"
                    f"You reached a streak of **{streak}**."
                ),
                color=discord.Color.red()
            )
            embed.set_footer(text="AkasaAirVirtual • Higher or Lower")

            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Higher ⬆️", style=discord.ButtonStyle.success, custom_id="hl_higher")
    async def higher(self, interaction: discord.Interaction, button: Button):
        await self.handle_guess(interaction, "higher")

    @discord.ui.button(label="Lower ⬇️", style=discord.ButtonStyle.danger, custom_id="hl_lower")
    async def lower(self, interaction: discord.Interaction, button: Button):
        await self.handle_guess(interaction, "lower")

    @discord.ui.button(label="End Game", emoji="🏁", style=discord.ButtonStyle.secondary, custom_id="hl_end")
    async def end_game(self, interaction: discord.Interaction, button: Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff can end the game.", ephemeral=True
            )

        game = active_games.pop(self.guild_id, None)
        if not game:
            return await interaction.response.send_message(
                "⚠️ No active game.", ephemeral=True
            )

        for child in self.children:
            child.disabled = True

        embed = discord.Embed(
            title="🏁 Game Ended",
            description=f"The number was **{game['secret']}**. Final streak: **{game['streak']}**.",
            color=discord.Color.greyple()
        )
        embed.set_footer(text="AkasaAirVirtual • Higher or Lower")

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        game = active_games.pop(self.guild_id, None)
        if not game:
            return
        try:
            channel = None
            for child in self.children:
                child.disabled = True
            # Can't easily edit the message on timeout without storing it
            # The buttons will just stop responding naturally
        except Exception:
            pass


# ================= COG =================

class HigherOrLower(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="higherorlower", description="Start a Higher or Lower number game")
    async def higherorlower(self, interaction: discord.Interaction):
        if interaction.guild.id in active_games:
            return await interaction.response.send_message(
                "⚠️ A game is already running! Finish it or ask staff to end it with the End Game button.",
                ephemeral=True
            )

        start_number = random.randint(MIN_NUMBER, MAX_NUMBER)
        secret = random.randint(MIN_NUMBER, MAX_NUMBER)

        # Make sure secret != start
        while secret == start_number:
            secret = random.randint(MIN_NUMBER, MAX_NUMBER)

        game = {
            "secret": secret,
            "current_number": start_number,
            "current_low": MIN_NUMBER,
            "current_high": MAX_NUMBER,
            "streak": 0,
            "last_user_id": None
        }

        active_games[interaction.guild.id] = game

        embed = build_embed(game, result_text="Is the secret number **higher** or **lower** than the number above?")
        view = HLView(interaction.guild.id)

        await interaction.response.send_message(embed=embed, view=view)

    # ================= LEADERBOARD =================

    @app_commands.command(name="hlleaderboard", description="Show the Higher or Lower leaderboard")
    async def hlleaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()

        rows = db_get_leaderboard(interaction.guild.id)

        if not rows:
            return await interaction.followup.send(
                "⚠️ No scores yet — start a game with `/higherorlower`!"
            )

        embed = discord.Embed(
            title="🏆 Higher or Lower — Leaderboard",
            description="Ranked by best streak",
            color=discord.Color.orange()
        )

        medals = ["🥇", "🥈", "🥉"]
        lines = []

        for i, row in enumerate(rows):
            member = interaction.guild.get_member(row["user_id"])
            name = member.display_name if member else f"<@{row['user_id']}>"
            medal = medals[i] if i < 3 else f"**#{i + 1}**"
            lines.append(
                f"{medal} {name} — 🔥 Best streak: **{row['best_streak']}** · ✅ Wins: **{row['total_wins']}**"
            )

        embed.description = "\n".join(lines)
        embed.set_footer(text="AkasaAirVirtual • Higher or Lower")

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(HigherOrLower(bot))
