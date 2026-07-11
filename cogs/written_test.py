import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
from supabase import create_client, Client
import os
import time
import asyncio
import random

SUPABASE_URL = "https://xljanwcgesjhdoaavmuo.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
STAFF_ROLE_ID = 1389824693388837035

PASS_SCORE = 13  # correct answers needed out of 15
QUESTION_TIMEOUT = 120  # seconds per question
QUESTIONS_PER_TEST = 15
DELETE_AFTER = 300  # delete question messages 5 minutes after result

# ================= QUESTION BANK (25 questions) =================

QUESTIONS = [
    {
        "question": "Which aircraft surface is used to reduce lift and increase drag on landing?",
        "options": ["Elevator", "Rudder", "Aileron", "Spoilers"],
        "answer": 3
    },
    {
        "question": "What's the main purpose of an APU (Auxiliary Power Unit)?",
        "options": ["Provide power on the ground", "Control hydraulics in-flight", "Boost engine thrust", "For sniffing in Infinite Flight"],
        "answer": 0
    },
    {
        "question": "What altitude should you maintain when flying IFR en route without ATC?",
        "options": ["Any altitude you choose", "Eastbound even / Westbound odd thousands", "Eastbound odd / Westbound even thousands", "Always FL180"],
        "answer": 2
    },
    {
        "question": "What is the maximum speed below 10,000 feet?",
        "options": ["200 knots", "300 knots", "250 knots", "350 knots"],
        "answer": 2
    },
    {
        "question": "What does 'Descend via the STAR' mean?",
        "options": ["Descend immediately to the runway", "Follow altitude and speed restrictions on the STAR", "Descend to 3000 feet", "Descend visually"],
        "answer": 1
    },
    {
        "question": "What does the V1 speed represent?",
        "options": ["Best climb speed", "Maximum takeoff speed", "Decision speed – continue takeoff above V1, abort below V1", "Rotation speed"],
        "answer": 2
    },
    {
        "question": "When should you arm the speed brakes (spoilers) on approach?",
        "options": ["Before takeoff", "After landing", "On final approach, before touchdown", "During climb"],
        "answer": 2
    },
    {
        "question": "What is the purpose of a SID (Standard Instrument Departure)?",
        "options": ["To guide aircraft from the gate to the runway", "To provide a standard route from takeoff to the enroute phase", "To descend into an airport", "To hold aircraft in a pattern"],
        "answer": 1
    },
    {
        "question": "What is the standard cruising altitude for IFR flights heading eastbound (magnetic track 000–179)?",
        "options": ["Odd thousands (e.g., FL310, FL330)", "Even thousands (e.g., FL320, FL340)", "Any altitude", "Always FL180"],
        "answer": 0
    },
    {
        "question": "What should you do if ATC instructs you to 'Hold Short' of a runway?",
        "options": ["Cross the runway", "Stop before the runway holding line", "Continue taxiing", "Take off"],
        "answer": 1
    },
    {
        "question": "What does 'Line Up and Wait' mean?",
        "options": ["Enter the runway and wait for takeoff clearance", "Taxi to the end of the runway", "Hold at the gate", "Execute a go-around"],
        "answer": 0
    },
    {
        "question": "What aircraft type does Akasa Air operate exclusively?",
        "options": ["Airbus A320neo", "Boeing 737 MAX 8", "Airbus A220", "Boeing 787 Dreamliner"],
        "answer": 1
    },
    {
        "question": "What is the range of the Boeing 737 MAX 8?",
        "options": ["2,000 km", "3,500 nm", "5,000 nm", "1,500 nm"],
        "answer": 1
    },
    {
        "question": "When did Akasa Air commence commercial operations?",
        "options": ["2020", "2021", "2022", "2023"],
        "answer": 2
    },
    {
        "question": "Who is the founder and CEO of Akasa Air?",
        "options": ["Rakesh Gangwal", "Vinay Dube", "Ajay Singh", "Sanjiv Kapoor"],
        "answer": 1
    },
    {
        "question": "What is the primary hub airport for Akasa Air's operations?",
        "options": ["Delhi (VIDP)", "Mumbai (VABB)", "Bengaluru (VOBL)", "Chennai (VOMM)"],
        "answer": 1
    },
    {
        "question": "How many passengers can the Akasa Air Boeing 737 MAX 8 typically seat?",
        "options": ["120", "150", "189", "220"],
        "answer": 2
    },
    {
        "question": "Which engine powers the Boeing 737 MAX 8?",
        "options": ["Pratt & Whitney PW1100G", "CFM International LEAP-1B", "Rolls-Royce Trent 1000", "General Electric CF6"],
        "answer": 1
    },
    {
        "question": "What is the maximum takeoff weight (MTOW) of the Boeing 737 MAX 8?",
        "options": ["60,000 kg", "82,627 kg", "100,000 kg", "70,000 kg"],
        "answer": 1
    },
    {
        "question": "Which Indian metro city is NOT currently served by Akasa Air?",
        "options": ["Kolkata (CCU)", "Chennai (MAA)", "Hyderabad (HYD)", "All of the above are served"],
        "answer": 3
    },
    {
        "question": "What does 'Expect vectors ILS Runway 27L' mean?",
        "options": ["You will fly the ILS approach visually", "ATC will provide radar vectors to intercept the ILS final approach course", "You must navigate to the ILS on your own", "You are cleared for the approach"],
        "answer": 1
    },
    {
        "question": "What does 'Runway in sight' mean when reporting to ATC?",
        "options": ["You can see the airport environment and will maintain visual contact", "You can see the runway lights only", "You are ready to land", "You need vectors to the runway"],
        "answer": 0
    },
    {
        "question": "The use of Check In is for aircraft flying ____________.",
        "options": ["On a filed IFR flight plan", "VFR", "In formation", "Only with center control"],
        "answer": 0
    },
    {
        "question": "You're working the Center sector that serves United 4245's destination airport which is currently staffed with Tower and Approach. Upon entering your center boundary, United 4245's first transmission should be ____ if they have a filed STAR.",
        "options": ["An approach request", "A check in", "An altitude request", "None of the above"],
        "answer": 1
    },
    {
        "question": "The ILS (Instrument Landing System) provides both lateral and vertical guidance.",
        "options": ["True", "False", "Only lateral guidance", "Only vertical guidance"],
        "answer": 0
    }
]


def get_db() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def is_staff(member: discord.Member) -> bool:
    return any(role.id == STAFF_ROLE_ID for role in member.roles)


OPTION_LABELS = ["A", "B", "C", "D"]
OPTION_EMOJIS = ["🇦", "🇧", "🇨", "🇩"]

# active sessions: user_id -> { q_index, score, answers }
active_sessions: dict = {}


# ================= SUPABASE HELPERS =================

def db_save_result(guild_id: int, user_id: int, score: int, passed: bool):
    db = get_db()
    try:
        res = db.table("written_test_scores").select("*").eq("guild_id", guild_id).eq("user_id", user_id).single().execute()
        existing = res.data
        db.table("written_test_scores").update({
            "attempts": existing["attempts"] + 1,
            "best_score": max(existing["best_score"], score),
            "last_score": score,
            "passed": existing["passed"] or passed
        }).eq("guild_id", guild_id).eq("user_id", user_id).execute()
    except Exception:
        db.table("written_test_scores").insert({
            "guild_id": guild_id,
            "user_id": user_id,
            "attempts": 1,
            "best_score": score,
            "last_score": score,
            "passed": passed
        }).execute()


def db_get_leaderboard(guild_id: int):
    try:
        res = get_db().table("written_test_scores").select("*").eq("guild_id", guild_id).order("best_score", desc=True).limit(10).execute()
        return res.data or []
    except Exception:
        return []


def db_get_user_score(guild_id: int, user_id: int):
    try:
        res = get_db().table("written_test_scores").select("*").eq("guild_id", guild_id).eq("user_id", user_id).single().execute()
        return res.data
    except Exception:
        return None
        
# ================= QUESTION VIEW =================

def build_question_embed(user_id: int) -> discord.Embed:
    session = active_sessions[user_id]
    q_index = session["q_index"]
    q = session["questions"][q_index]
    total = len(session["questions"])
    deadline = session.get("question_deadline", 0)

    embed = discord.Embed(
        title="✍️ Akasa Air Virtual — Written Test",
        description=f"**Question {q_index + 1} of {total}**\n\n{q['question']}",
        color=discord.Color.orange()
    )

    for i, opt in enumerate(q["options"]):
        embed.add_field(
            name=f"{OPTION_EMOJIS[i]} {OPTION_LABELS[i]}",
            value=opt,
            inline=False
        )

    embed.add_field(
        name="⏱️ Time Remaining",
        value=f"<t:{deadline}:R>" if deadline else f"{QUESTION_TIMEOUT} seconds",
        inline=False
    )

    embed.set_footer(
        text=f"Score so far: {session['score']}/{q_index} • AkasaAirVirtual Written Test"
    )
    return embed


class QuestionView(View):
    def __init__(self, user_id: int, guild_id: int):
        super().__init__(timeout=QUESTION_TIMEOUT)
        self.user_id = user_id
        self.guild_id = guild_id
        self.message: discord.Message = None  # set after sending

        for i, label in enumerate(OPTION_LABELS):
            btn = Button(
                label=f"{OPTION_EMOJIS[i]}  {label}",
                style=discord.ButtonStyle.primary,
                custom_id=f"test_{user_id}_{i}"
            )
            btn.callback = self._make_callback(i)
            self.add_item(btn)

    def _make_callback(self, option_index: int):
        async def callback(interaction: discord.Interaction):
            # Only the test owner can answer
            if interaction.user.id != self.user_id:
                return await interaction.response.send_message(
                    f"❌ This test belongs to <@{self.user_id}>. Run `/startwrittentest` to start your own!",
                    ephemeral=True
                )

            session = active_sessions.get(self.user_id)
            if not session:
                return await interaction.response.send_message(
                    "⚠️ Your test session has expired. Run `/startwrittentest` to begin again.",
                    ephemeral=True
                )

            q_index = session["q_index"]
            q = session["questions"][q_index]
            correct = option_index == q["answer"]

            if correct:
                session["score"] += 1

            session["answers"].append({
                "q_index": q_index,
                "chosen": option_index,
                "correct": correct
            })

            # Disable buttons and highlight correct/wrong
            for child in self.children:
                child.disabled = True
                if isinstance(child, Button):
                    idx = int(child.custom_id.split("_")[-1])
                    if idx == q["answer"]:
                        child.style = discord.ButtonStyle.success
                    elif idx == option_index and not correct:
                        child.style = discord.ButtonStyle.danger
                    else:
                        child.style = discord.ButtonStyle.secondary

            result_text = "✅ Correct!" if correct else f"❌ Wrong! The correct answer was **{OPTION_LABELS[q['answer']]}**."
            embed = build_question_embed(self.user_id)
            embed.add_field(name="\u200b", value=result_text, inline=False)

            session["q_index"] += 1
            self.stop()  # stop timeout loop for this view
            await interaction.response.edit_message(embed=embed, view=self)

            total = len(session["questions"])
            if session["q_index"] < total:
                session["question_deadline"] = int(time.time()) + QUESTION_TIMEOUT
                next_embed = build_question_embed(self.user_id)
                next_view = QuestionView(self.user_id, self.guild_id)
                msg = await interaction.followup.send(embed=next_embed, view=next_view, ephemeral=False)
                next_view.message = msg
                session["message_ids"].append(msg.id)
                session["channel_id"] = interaction.channel.id
            else:
                await self._finish_test(interaction)

        return callback

    async def _finish_test(self, interaction: discord.Interaction):
        session = active_sessions.pop(self.user_id, {})
        score = session.get("score", 0)
        answers = session.get("answers", [])
        questions = session.get("questions", QUESTIONS[:16])
        total = len(questions)
        passed = score >= PASS_SCORE
        percentage = round((score / total) * 100)

        db_save_result(self.guild_id, self.user_id, score, passed)

        if passed:
            color = discord.Color.green()
            result_title = "✅ PASSED"
            result_desc = (
                f"Congratulations <@{self.user_id}>! "
                "You have passed the Akasa Air Virtual written test. ✈️\n"
                "Our staff team will be in touch shortly."
            )
        else:
            color = discord.Color.red()
            result_title = "❌ FAILED"
            result_desc = (
                f"<@{self.user_id}> did not reach the pass mark this time.\n"
                f"You need at least **{PASS_SCORE}/{total}** correct to pass. Keep studying and try again!"
            )

        embed = discord.Embed(
            title=f"📋 Written Test Complete — {result_title}",
            description=result_desc,
            color=color
        )

        embed.add_field(name="🎯 Score", value=f"**{score} / {total}**", inline=True)
        embed.add_field(name="📊 Percentage", value=f"**{percentage}%**", inline=True)
        embed.add_field(name="✅ Pass Mark", value=f"**{PASS_SCORE}/{total}**", inline=True)

        correct_nums = [str(a["q_index"] + 1) for a in answers if a["correct"]]
        wrong_nums = [str(a["q_index"] + 1) for a in answers if not a["correct"]]
        skipped = total - len(answers)

        if correct_nums:
            embed.add_field(
                name=f"✅ Correct ({len(correct_nums)})",
                value=", ".join(f"Q{n}" for n in correct_nums),
                inline=False
            )
        if wrong_nums:
            embed.add_field(
                name=f"❌ Wrong ({len(wrong_nums)})",
                value=", ".join(f"Q{n}" for n in wrong_nums),
                inline=False
            )
        if skipped:
            embed.add_field(
                name=f"⏩ Skipped (timed out) ({skipped})",
                value=f"{skipped} question(s) were skipped due to timeout.",
                inline=False
            )

        embed.add_field(
            name="\u200b",
            value=f"⚠️ All question messages will be deleted in **5 minutes**.",
            inline=False
        )

        embed.set_footer(text="AkasaAirVirtual • Written Test")

        result_msg = await interaction.followup.send(embed=embed, ephemeral=False)

        # Schedule deletion of question messages only after 5 minutes
        # Result embed is intentionally NOT included — it stays permanently
        message_ids = session.get("message_ids", [])
        channel_id = session.get("channel_id")
        asyncio.get_event_loop().create_task(
            self._delete_messages_later(interaction.client, channel_id, message_ids)
        )

    @staticmethod
    async def _delete_messages_later(bot, channel_id: int, message_ids: list):
        """Delete only the question messages after 5 minutes. Result embed is kept."""
        await asyncio.sleep(DELETE_AFTER)
        channel = bot.get_channel(channel_id) if bot and channel_id else None
        if channel:
            for msg_id in message_ids:
                try:
                    msg = await channel.fetch_message(msg_id)
                    await msg.delete()
                except Exception:
                    pass

    async def on_timeout(self):
        """Auto-advance to next question when time runs out."""
        session = active_sessions.get(self.user_id)
        if not session:
            return

        q_index = session["q_index"]
        questions = session["questions"]
        q = questions[q_index]

        # Record as skipped (no answer)
        session["answers"].append({
            "q_index": q_index,
            "chosen": None,
            "correct": False
        })
        session["q_index"] += 1

        # Disable buttons on the timed-out message
        for child in self.children:
            child.disabled = True
            if isinstance(child, Button):
                idx = int(child.custom_id.split("_")[-1])
                if idx == q["answer"]:
                    child.style = discord.ButtonStyle.success
                else:
                    child.style = discord.ButtonStyle.secondary

        if self.message:
            try:
                timeout_embed = discord.Embed(
                    title="✍️ Akasa Air Virtual — Written Test",
                    description=f"**Question {q_index + 1} of {len(questions)}**\n\n{q['question']}",
                    color=discord.Color.red()
                )
                for i, opt in enumerate(q["options"]):
                    timeout_embed.add_field(name=f"{OPTION_EMOJIS[i]} {OPTION_LABELS[i]}", value=opt, inline=False)
                timeout_embed.add_field(name="⏱️ Timed Out", value=f"⏩ Time is up! The answer was **{OPTION_LABELS[q['answer']]}**.", inline=False)
                timeout_embed.set_footer(text="AkasaAirVirtual • Written Test")
                await self.message.edit(embed=timeout_embed, view=self)
            except Exception:
                pass

        total = len(questions)
        if session["q_index"] < total:
            # Send next question via the bot since we have no interaction here
            channel = self.message.channel if self.message else None
            if channel:
                session["question_deadline"] = int(time.time()) + QUESTION_TIMEOUT
                next_embed = build_question_embed(self.user_id)
                next_view = QuestionView(self.user_id, self.guild_id)
                try:
                    msg = await channel.send(embed=next_embed, view=next_view)
                    next_view.message = msg
                    session["message_ids"].append(msg.id)
                    session["channel_id"] = channel.id
                except Exception:
                    active_sessions.pop(self.user_id, None)
        else:
            # All questions done via timeout — post final result
            session_copy = active_sessions.pop(self.user_id, session)
            score = session_copy.get("score", 0)
            answers = session_copy.get("answers", [])
            questions_list = session_copy.get("questions", questions)
            total_q = len(questions_list)
            passed = score >= PASS_SCORE
            percentage = round((score / total_q) * 100)

            db_save_result(self.guild_id, self.user_id, score, passed)

            color = discord.Color.green() if passed else discord.Color.red()
            result_title = "✅ PASSED" if passed else "❌ FAILED"
            result_desc = (
                f"Congratulations <@{self.user_id}>! You passed the written test. ✈️\nStaff will be in touch shortly."
                if passed else
                f"<@{self.user_id}> did not reach the pass mark. You need **{PASS_SCORE}/{total_q}** correct."
            )

            embed = discord.Embed(title=f"📋 Written Test Complete — {result_title}", description=result_desc, color=color)
            embed.add_field(name="🎯 Score", value=f"**{score} / {total_q}**", inline=True)
            embed.add_field(name="📊 Percentage", value=f"**{percentage}%**", inline=True)
            embed.add_field(name="✅ Pass Mark", value=f"**{PASS_SCORE}/{total_q}**", inline=True)
            skipped = sum(1 for a in answers if a["chosen"] is None)
            if skipped:
                embed.add_field(name=f"⏩ Skipped ({skipped})", value=f"{skipped} question(s) timed out.", inline=False)
            embed.add_field(name="\u200b", value="⚠️ All question messages will be deleted in **5 minutes**.", inline=False)
            embed.set_footer(text="AkasaAirVirtual • Written Test")

            channel = self.message.channel if self.message else None
            if channel:
                try:
                    await channel.send(embed=embed)
                    message_ids = session_copy.get("message_ids", [])
                    bot = channel.guild._state._get_client()
                    asyncio.get_event_loop().create_task(
                        QuestionView._delete_messages_later(bot, channel.id, message_ids)
                    )
                except Exception:
                    pass

# ================= COG =================

class WrittenTest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="startwrittentest", description="Start the Akasa Air Virtual written test")
    async def startwrittentest(self, interaction: discord.Interaction):
        if self.user_id_in_session(interaction.user.id):
            return await interaction.response.send_message(
                "⚠️ You already have an active test session! Answer the current question first.",
                ephemeral=True
            )

        active_sessions[interaction.user.id] = {
            "q_index": 0,
            "score": 0,
            "answers": [],
            "guild_id": interaction.guild.id,
            "channel_id": interaction.channel.id,
            "message_ids": [],
            "questions": random.sample(QUESTIONS, min(QUESTIONS_PER_TEST, len(QUESTIONS))),
            "question_deadline": int(time.time()) + QUESTION_TIMEOUT
        }

        session = active_sessions[interaction.user.id]
        total_q = len(session["questions"])

        intro_embed = discord.Embed(
            title="✍️ Akasa Air Virtual — Written Test",
            description=(
                f"Welcome <@{interaction.user.id}> to the **Akasa Air Virtual Written Test**!\n\n"
                f"📋 **{total_q} questions** covering aviation knowledge and Akasa Air.\n"
                f"✅ **Pass mark:** {PASS_SCORE} correct answers\n"
                f"⏱️ **{QUESTION_TIMEOUT} seconds** per question — unanswered questions auto-skip.\n\n"
                "Only you can click your own buttons.\n"
                "Good luck! ✈️"
            ),
            color=discord.Color.orange()
        )
        intro_embed.set_footer(text="AkasaAirVirtual • Written Test")

        await interaction.response.send_message(embed=intro_embed, ephemeral=False)
        intro_msg = await interaction.original_response()
        session["message_ids"].append(intro_msg.id)

        first_embed = build_question_embed(interaction.user.id)
        first_view = QuestionView(interaction.user.id, interaction.guild.id)
        first_msg = await interaction.followup.send(embed=first_embed, view=first_view, ephemeral=False)
        first_view.message = first_msg
        session["message_ids"].append(first_msg.id)

    def user_id_in_session(self, user_id: int) -> bool:
        return user_id in active_sessions

    # ================= MY SCORE =================

    @app_commands.command(name="mytestscore", description="Check your written test score")
    async def mytestscore(self, interaction: discord.Interaction):
        row = db_get_user_score(interaction.guild.id, interaction.user.id)

        if not row:
            return await interaction.response.send_message(
                "⚠️ You haven't taken the written test yet. Run `/startwrittentest` to begin!",
                ephemeral=True
            )

        embed = discord.Embed(
            title="📋 Your Written Test Score",
            color=discord.Color.green() if row["passed"] else discord.Color.red()
        )
        embed.add_field(name="🏅 Best Score", value=f"**{row['best_score']}/{QUESTIONS_PER_TEST}**", inline=True)
        embed.add_field(name="📊 Last Score", value=f"**{row['last_score']}/{QUESTIONS_PER_TEST}**", inline=True)
        embed.add_field(name="🔄 Attempts", value=str(row["attempts"]), inline=True)
        embed.add_field(name="Result", value="✅ PASSED" if row["passed"] else "❌ Not yet passed", inline=True)
        embed.set_footer(text="AkasaAirVirtual • Written Test")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ================= LEADERBOARD =================

    @app_commands.command(name="testleaderboard", description="Show the written test leaderboard")
    async def testleaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()

        rows = db_get_leaderboard(interaction.guild.id)

        if not rows:
            return await interaction.followup.send(
                "⚠️ No scores yet — run `/startwrittentest` to take the test!"
            )

        embed = discord.Embed(
            title="🏆 Written Test — Leaderboard",
            description="Ranked by best score",
            color=discord.Color.orange()
        )

        medals = ["🥇", "🥈", "🥉"]
        lines = []

        for i, row in enumerate(rows):
            member = interaction.guild.get_member(row["user_id"])
            name = member.display_name if member else f"<@{row['user_id']}>"
            medal = medals[i] if i < 3 else f"**#{i + 1}**"
            status = "✅" if row["passed"] else "❌"
            lines.append(
                f"{medal} {name} — **{row['best_score']}/{QUESTIONS_PER_TEST}** {status} · {row['attempts']} attempt{'s' if row['attempts'] != 1 else ''}"
            )

        embed.description = "\n".join(lines)
        embed.set_footer(text="AkasaAirVirtual • Written Test")

        await interaction.followup.send(embed=embed)

    # ================= VIEW RESULTS (staff) =================

    @app_commands.command(name="viewtestresult", description="View a member's test results (staff only)")
    @app_commands.describe(member="The member to look up")
    async def viewtestresult(self, interaction: discord.Interaction, member: discord.Member):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Staff only.", ephemeral=True)

        row = db_get_user_score(interaction.guild.id, member.id)

        if not row:
            return await interaction.response.send_message(
                f"⚠️ {member.mention} has not taken the written test yet.", ephemeral=True
            )

        embed = discord.Embed(
            title=f"📋 Test Results — {member.display_name}",
            color=discord.Color.green() if row["passed"] else discord.Color.red()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="🏅 Best Score", value=f"**{row['best_score']}/{QUESTIONS_PER_TEST}**", inline=True)
        embed.add_field(name="📊 Last Score", value=f"**{row['last_score']}/{QUESTIONS_PER_TEST}**", inline=True)
        embed.add_field(name="🔄 Attempts", value=str(row["attempts"]), inline=True)
        embed.add_field(name="Result", value="✅ PASSED" if row["passed"] else "❌ Not yet passed", inline=True)
        embed.set_footer(text="AkasaAirVirtual • Written Test")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(WrittenTest(bot))
