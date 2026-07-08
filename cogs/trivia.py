import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
from supabase import create_client, Client
import os
import random
import asyncio

STAFF_ROLE_ID = 1389824693388837035
SUPABASE_URL = "https://xljanwcgesjhdoaavmuo.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

QUESTION_TIMEOUT = 30  # seconds


def get_db() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def is_staff(member: discord.Member) -> bool:
    return any(role.id == STAFF_ROLE_ID for role in member.roles)


# ================= QUESTION BANK =================

QUESTIONS = [
    {
        "question": "What does ICAO stand for?",
        "options": ["International Civil Aviation Organization", "International Commercial Aircraft Operations", "Integrated Civil Airway Organization", "International Civilian Airspace Office"],
        "answer": 0
    },
    {
        "question": "What is the ICAO code for London Heathrow Airport?",
        "options": ["EGLL", "EGLC", "EGKK", "EGSS"],
        "answer": 0
    },
    {
        "question": "What is the standard cruising altitude for most commercial aircraft?",
        "options": ["10,000–15,000 ft", "20,000–25,000 ft", "35,000–42,000 ft", "50,000–55,000 ft"],
        "answer": 2
    },
    {
        "question": "What does QNH stand for in aviation?",
        "options": ["Queue Navigation Height", "Barometric pressure adjusted to sea level", "Quadrant Navigation Heading", "Quality Night Humidity"],
        "answer": 1
    },
    {
        "question": "Which aircraft is nicknamed the 'Jumbo Jet'?",
        "options": ["Boeing 737", "Airbus A380", "Boeing 747", "Douglas DC-10"],
        "answer": 2
    },
    {
        "question": "What does ATIS stand for?",
        "options": ["Automatic Terminal Information Service", "Air Traffic Identification System", "Airborne Terrain Imaging System", "Automated Traffic Integration Service"],
        "answer": 0
    },
    {
        "question": "What colour are taxiway centreline lights?",
        "options": ["Blue", "White", "Green", "Yellow"],
        "answer": 2
    },
    {
        "question": "What is the phonetic alphabet word for the letter 'A'?",
        "options": ["Alpha", "Able", "Apex", "Arrow"],
        "answer": 0
    },
    {
        "question": "What does 'VFR' stand for?",
        "options": ["Very Fast Route", "Visual Flight Rules", "Vertical Flight Reference", "Vector Flight Radar"],
        "answer": 1
    },
    {
        "question": "Which country has the busiest airspace in the world?",
        "options": ["China", "United Kingdom", "United States", "Germany"],
        "answer": 2
    },
    {
        "question": "What does 'Mayday' signal in aviation?",
        "options": ["Request for fuel", "Distress signal — life-threatening emergency", "Weather check request", "Permission to land"],
        "answer": 1
    },
    {
        "question": "What is the ICAO code for Dubai International Airport?",
        "options": ["OMDB", "OMDW", "OMAA", "OMFJ"],
        "answer": 0
    },
    {
        "question": "What does a flashing red light signal to an aircraft on the ground?",
        "options": ["Cleared to take off", "Taxi clear of runway", "Stop", "Return to start"],
        "answer": 1
    },
    {
        "question": "Akasa Air is based in which country?",
        "options": ["Pakistan", "Sri Lanka", "India", "Bangladesh"],
        "answer": 2
    },
    {
        "question": "What is the ICAO code for Indira Gandhi International Airport (Delhi)?",
        "options": ["VABB", "VIDP", "VOBL", "VOMM"],
        "answer": 1
    },
    {
        "question": "What does 'ILS' stand for?",
        "options": ["Instrument Landing System", "Integrated Launch Sequence", "Internal Lift System", "Inbound Landing Signal"],
        "answer": 0
    },
    {
        "question": "What is the minimum safe altitude abbreviation used in aviation?",
        "options": ["MCA", "MSA", "MDA", "MEA"],
        "answer": 1
    },
    {
        "question": "What is the speed of sound at sea level approximately?",
        "options": ["500 knots", "660 knots", "760 mph", "900 mph"],
        "answer": 2
    },
    {
        "question": "Which aircraft has the longest range in commercial aviation?",
        "options": ["Boeing 777X", "Airbus A350-900ULR", "Boeing 787-9", "Airbus A380"],
        "answer": 1
    },
    {
        "question": "What does 'SID' stand for in aviation?",
        "options": ["Standard Instrument Departure", "Signal Identification Data", "System Information Display", "Secondary ILS Direction"],
        "answer": 0
    },
    {
        "question": "What colour are runway edge lights?",
        "options": ["Green", "Blue", "Red", "White"],
        "answer": 3
    },
    {
        "question": "What does 'STAR' stand for in aviation?",
        "options": ["Standard Terminal Arrival Route", "Signal Tracking and Radar", "Standard Traffic Approach Route", "Secondary Terminal Approach Route"],
        "answer": 0
    },
    {
        "question": "What is the ICAO code for Singapore Changi Airport?",
        "options": ["WSSS", "WSSL", "WIDD", "WMKK"],
        "answer": 0
    },
    {
        "question": "What does a pilot call out when the aircraft reaches decision altitude on an ILS approach?",
        "options": ["Clear", "Minimums", "Decision", "Runway in sight"],
        "answer": 1
    },
    {
        "question": "What is the purpose of winglets on commercial aircraft?",
        "options": ["Increase lift at low speed", "Reduce aerodynamic drag and improve fuel efficiency", "Improve roll control", "Reduce weight"],
        "answer": 1
    },
    {
        "question": "What does 'ATC' stand for?",
        "options": ["Air Traffic Command", "Air Traffic Control", "Aircraft Technical Check", "Airborne Tracking Centre"],
        "answer": 1
    },
    {
        "question": "What is the ICAO code for Mumbai Chhatrapati Shivaji International Airport?",
        "options": ["VIDP", "VABB", "VOBL", "VOMM"],
        "answer": 1
    },
    {
        "question": "Which aircraft manufacturer produces the A320 family?",
        "options": ["Boeing", "Embraer", "Airbus", "Bombardier"],
        "answer": 2
    },
    {
        "question": "What colour is the left (port) navigation light on an aircraft?",
        "options": ["White", "Green", "Red", "Blue"],
        "answer": 2
    },
    {
        "question": "What does 'ETA' stand for in aviation?",
        "options": ["Estimated Time of Arrival", "Engine Thrust Adjustment", "Emergency Terrain Alert", "Electronic Traffic Avoidance"],
        "answer": 0
    }
]

OPTION_LABELS = ["🇦", "🇧", "🇨", "🇩"]

# active_games: guild_id -> { answer_index, answered_user_ids, task }
active_games: dict = {}


# ================= SUPABASE HELPERS =================

def db_add_point(guild_id: int, user_id: int):
    db = get_db()
    try:
        res = db.table("trivia_scores").select("*").eq("guild_id", guild_id).eq("user_id", user_id).single().execute()
        existing = res.data
        db.table("trivia_scores").update({
            "points": existing["points"] + 1
        }).eq("guild_id", guild_id).eq("user_id", user_id).execute()
    except Exception:
        db.table("trivia_scores").insert({
            "guild_id": guild_id,
            "user_id": user_id,
            "points": 1
        }).execute()


def db_get_leaderboard(guild_id: int):
    try:
        res = get_db().table("trivia_scores").select("*").eq("guild_id", guild_id).order("points", desc=True).limit(10).execute()
        return res.data or []
    except Exception:
        return []


# ================= TRIVIA VIEW =================

class TriviaView(View):
    def __init__(self, guild_id: int, answer_index: int, q_index: int):
        super().__init__(timeout=QUESTION_TIMEOUT)
        self.guild_id = guild_id
        self.answer_index = answer_index
        self.answered_user_ids = set()
        self.winner = None

        for i, label in enumerate(OPTION_LABELS):
            btn = Button(
                label=label,
                style=discord.ButtonStyle.primary,
                custom_id=f"trivia_{q_index}_{i}"
            )
            btn.callback = self._make_callback(i)
            self.add_item(btn)

    def _make_callback(self, option_index: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id in self.answered_user_ids:
                return await interaction.response.send_message(
                    "⚠️ You have already answered this question!", ephemeral=True
                )

            self.answered_user_ids.add(interaction.user.id)

            if option_index == self.answer_index:
                # Correct — first correct answer wins
                if self.winner is None:
                    self.winner = interaction.user
                    db_add_point(self.guild_id, interaction.user.id)

                    # Disable all buttons
                    for child in self.children:
                        child.disabled = True
                        if isinstance(child, Button):
                            child.style = discord.ButtonStyle.secondary

                    # Mark winning button green
                    self.children[self.answer_index].style = discord.ButtonStyle.success

                    active_games.pop(self.guild_id, None)

                    await interaction.response.edit_message(view=self)
                    await interaction.followup.send(
                        f"✅ {interaction.user.mention} got it right! **+1 point** 🎉\n"
                        f"The answer was **{OPTION_LABELS[self.answer_index]}**.",
                    )
                    self.stop()
                else:
                    await interaction.response.send_message(
                        f"✅ Correct! But {self.winner.mention} was first. Better luck next time!",
                        ephemeral=True
                    )
            else:
                await interaction.response.send_message(
                    f"❌ Wrong answer! Keep trying.", ephemeral=True
                )

        return callback

    async def on_timeout(self):
        active_games.pop(self.guild_id, None)

        for child in self.children:
            child.disabled = True
            if isinstance(child, Button):
                child.style = discord.ButtonStyle.secondary

        # Mark correct answer red on timeout
        if self.answer_index < len(self.children):
            self.children[self.answer_index].style = discord.ButtonStyle.danger

        try:
            await self.message.edit(
                content=f"⏱️ Time's up! Nobody answered in time. The answer was **{OPTION_LABELS[self.answer_index]}**.",
                view=self
            )
        except Exception:
            pass


# ================= COG =================

class Trivia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="trivia", description="Start an aviation trivia question (staff only)")
    async def trivia(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff can start a trivia question.", ephemeral=True
            )

        if interaction.guild.id in active_games:
            return await interaction.response.send_message(
                "⚠️ A trivia question is already active! Wait for it to finish or time out.",
                ephemeral=True
            )

        q_index = random.randint(0, len(QUESTIONS) - 1)
        q = QUESTIONS[q_index]

        # Shuffle options and track new answer index
        options = list(enumerate(q["options"]))
        random.shuffle(options)
        shuffled_options = [opt for _, opt in options]
        original_indices = [orig_i for orig_i, _ in options]
        new_answer_index = original_indices.index(q["answer"])

        embed = discord.Embed(
            title="✈️ Aviation Trivia!",
            description=f"**{q['question']}**",
            color=discord.Color.orange()
        )

        for i, opt in enumerate(shuffled_options):
            embed.add_field(
                name=f"{OPTION_LABELS[i]}",
                value=opt,
                inline=False
            )

        embed.set_footer(text=f"⏱️ You have {QUESTION_TIMEOUT} seconds to answer! • AkasaAirVirtual Trivia")

        view = TriviaView(interaction.guild.id, new_answer_index, q_index)
        active_games[interaction.guild.id] = True

        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    # ================= LEADERBOARD =================

    @app_commands.command(name="trivialeaderboard", description="Show the Aviation Trivia leaderboard")
    async def trivialeaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()

        rows = db_get_leaderboard(interaction.guild.id)

        if not rows:
            return await interaction.followup.send(
                "⚠️ No scores yet — start a game with `/trivia`!"
            )

        embed = discord.Embed(
            title="🏆 Aviation Trivia — Leaderboard",
            description="Ranked by total correct answers",
            color=discord.Color.orange()
        )

        medals = ["🥇", "🥈", "🥉"]
        lines = []

        for i, row in enumerate(rows):
            member = interaction.guild.get_member(row["user_id"])
            name = member.display_name if member else f"<@{row['user_id']}>"
            medal = medals[i] if i < 3 else f"**#{i + 1}**"
            pts = row["points"]
            lines.append(f"{medal} {name} — **{pts}** point{'s' if pts != 1 else ''}")

        embed.description = "\n".join(lines)
        embed.set_footer(text="AkasaAirVirtual • Aviation Trivia")

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Trivia(bot))
