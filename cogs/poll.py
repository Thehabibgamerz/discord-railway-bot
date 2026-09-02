import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta
import os
import re

SUPABASE_URL = "https://xljanwcgesjhdoaavmuo.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

OPTION_EMOJIS = ["🇦", "🇧", "🇨", "🇩", "🇪"]
BAR_FILLED = "█"
BAR_EMPTY = "░"
BAR_LENGTH = 10


def get_db() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def parse_duration(text: str) -> int | None:
    text = text.strip().lower()
    match = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", text)
    if not match or not any(match.groups()):
        return None
    total = 0
    if match.group(1):
        total += int(match.group(1)) * 3600
    if match.group(2):
        total += int(match.group(2)) * 60
    if match.group(3):
        total += int(match.group(3))
    return total if total > 0 else None


def format_duration(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    if s: parts.append(f"{s}s")
    return " ".join(parts) or "0s"


def make_bar(votes: int, total: int) -> str:
    if total == 0:
        filled = 0
    else:
        filled = round((votes / total) * BAR_LENGTH)
    return BAR_FILLED * filled + BAR_EMPTY * (BAR_LENGTH - filled)


# ================= SUPABASE HELPERS =================

def db_create_poll(guild_id, channel_id, question, options, created_by, ends_at):
    res = get_db().table("polls").insert({
        "guild_id": guild_id,
        "channel_id": channel_id,
        "question": question,
        "options": options,
        "created_by": created_by,
        "ends_at": ends_at,
        "ended": False
    }).execute()
    return res.data[0] if res.data else None


def db_set_message_id(poll_id, message_id):
    get_db().table("polls").update({"message_id": message_id}).eq("id", poll_id).execute()


def db_get_poll(poll_id):
    try:
        res = get_db().table("polls").select("*").eq("id", poll_id).single().execute()
        return res.data
    except Exception:
        return None


def db_get_active_polls():
    try:
        now = datetime.now(timezone.utc).isoformat()
        res = get_db().table("polls").select("*").eq("ended", False).lte("ends_at", now).execute()
        return res.data or []
    except Exception:
        return []


def db_get_all_active_polls():
    try:
        res = get_db().table("polls").select("*").eq("ended", False).execute()
        return res.data or []
    except Exception:
        return []


def db_mark_ended(poll_id):
    get_db().table("polls").update({"ended": True}).eq("id", poll_id).execute()


def db_vote(poll_id, user_id, option_index):
    try:
        get_db().table("poll_votes").upsert({
            "poll_id": poll_id,
            "user_id": user_id,
            "option_index": option_index
        }).execute()
        return True
    except Exception:
        return False


def db_get_votes(poll_id):
    try:
        res = get_db().table("poll_votes").select("*").eq("poll_id", poll_id).execute()
        return res.data or []
    except Exception:
        return []


def db_get_user_vote(poll_id, user_id):
    try:
        res = get_db().table("poll_votes").select("option_index").eq("poll_id", poll_id).eq("user_id", user_id).single().execute()
        return res.data["option_index"] if res.data else None
    except Exception:
        return None


# ================= EMBED BUILDERS =================

def build_poll_embed(poll: dict, votes: list, ended: bool = False) -> discord.Embed:
    options = poll["options"]
    total = len(votes)
    ends_at = datetime.fromisoformat(str(poll["ends_at"]).replace("Z", "+00:00").replace(" ", "T"))
    timestamp = int(ends_at.timestamp())

    color = discord.Color.greyple() if ended else discord.Color.orange()
    status = "🔒 Poll Ended" if ended else "🟢 Live Poll"

    embed = discord.Embed(
        title=f"📊 {poll['question']}",
        color=color
    )

    # Count votes per option
    vote_counts = {i: 0 for i in range(len(options))}
    for v in votes:
        idx = v["option_index"]
        if idx in vote_counts:
            vote_counts[idx] += 1

    for i, option in enumerate(options):
        count = vote_counts[i]
        pct = round((count / total) * 100) if total > 0 else 0
        bar = make_bar(count, total)
        embed.add_field(
            name=f"{OPTION_EMOJIS[i]} {option}",
            value=f"`{bar}` **{count}** vote{'s' if count != 1 else ''} ({pct}%)",
            inline=False
        )

    embed.add_field(
        name="📊 Total Votes",
        value=str(total),
        inline=True
    )

    if ended:
        embed.add_field(name="🔒 Status", value="Poll has ended", inline=True)
        # Find winner
        if total > 0:
            winner_idx = max(vote_counts, key=vote_counts.get)
            if vote_counts[winner_idx] > 0:
                embed.add_field(
                    name="🏆 Winner",
                    value=f"{OPTION_EMOJIS[winner_idx]} **{options[winner_idx]}**",
                    inline=True
                )
    else:
        embed.add_field(name="⏰ Ends", value=f"<t:{timestamp}:R>", inline=True)
        embed.add_field(name="🟢 Status", value=status, inline=True)

    embed.set_footer(text=f"Poll ID: #{poll['id']} • AkasaAirVirtual")
    return embed


def build_results_embed(poll: dict, votes: list) -> discord.Embed:
    options = poll["options"]
    total = len(votes)

    vote_counts = {i: 0 for i in range(len(options))}
    for v in votes:
        idx = v["option_index"]
        if idx in vote_counts:
            vote_counts[idx] += 1

    embed = discord.Embed(
        title=f"📊 Poll Results — {poll['question']}",
        color=discord.Color.gold()
    )

    sorted_options = sorted(vote_counts.items(), key=lambda x: x[1], reverse=True)
    medals = ["🥇", "🥈", "🥉"]

    for rank, (i, count) in enumerate(sorted_options):
        pct = round((count / total) * 100) if total > 0 else 0
        bar = make_bar(count, total)
        medal = medals[rank] if rank < 3 else f"#{rank+1}"
        embed.add_field(
            name=f"{medal} {OPTION_EMOJIS[i]} {options[i]}",
            value=f"`{bar}` **{count}** vote{'s' if count != 1 else ''} ({pct}%)",
            inline=False
        )

    embed.add_field(name="👥 Total Votes", value=str(total), inline=True)

    if total > 0:
        winner_idx = sorted_options[0][0]
        embed.add_field(
            name="🏆 Winner",
            value=f"{OPTION_EMOJIS[winner_idx]} **{options[winner_idx]}**",
            inline=True
        )

    embed.set_footer(text=f"Poll #{poll['id']} ended • AkasaAirVirtual")
    return embed


# ================= POLL VIEW =================

class PollView(View):
    def __init__(self, poll_id: int, options: list):
        super().__init__(timeout=None)
        self.poll_id = poll_id

        for i, option in enumerate(options[:5]):
            btn = Button(
                label=option[:80],
                emoji=OPTION_EMOJIS[i],
                style=discord.ButtonStyle.primary,
                custom_id=f"poll_{poll_id}_{i}"
            )
            btn.callback = self._make_callback(i)
            self.add_item(btn)

    def _make_callback(self, option_index: int):
        async def callback(interaction: discord.Interaction):
            poll = db_get_poll(self.poll_id)
            if not poll:
                return await interaction.response.send_message("⚠️ Poll not found.", ephemeral=True)

            if poll.get("ended"):
                return await interaction.response.send_message("🔒 This poll has already ended.", ephemeral=True)

            # Check if poll expired
            ends_at = datetime.fromisoformat(str(poll["ends_at"]).replace("Z", "+00:00").replace(" ", "T"))
            if datetime.now(timezone.utc) > ends_at:
                return await interaction.response.send_message("🔒 This poll has already ended.", ephemeral=True)

            existing_vote = db_get_user_vote(self.poll_id, interaction.user.id)

            db_vote(self.poll_id, interaction.user.id, option_index)
            votes = db_get_votes(self.poll_id)
            embed = build_poll_embed(poll, votes)

            await interaction.response.edit_message(embed=embed, view=self)

            options = poll["options"]
            if existing_vote is not None and existing_vote != option_index:
                await interaction.followup.send(
                    f"🔄 Vote changed to {OPTION_EMOJIS[option_index]} **{options[option_index]}**",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"✅ Voted for {OPTION_EMOJIS[option_index]} **{options[option_index]}**",
                    ephemeral=True
                )

        return callback


# ================= COG =================

class Poll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_polls.start()

    async def cog_unload(self):
        self.check_polls.cancel()

    @tasks.loop(seconds=30)
    async def check_polls(self):
        for poll in db_get_active_polls():
            try:
                db_mark_ended(poll["id"])
                channel = self.bot.get_channel(int(poll["channel_id"]))
                if not channel:
                    continue

                votes = db_get_votes(poll["id"])
                results_embed = build_results_embed(poll, votes)

                # Edit original message to show ended state
                if poll.get("message_id"):
                    try:
                        msg = await channel.fetch_message(int(poll["message_id"]))
                        ended_embed = build_poll_embed(poll, votes, ended=True)
                        # Disable all buttons
                        disabled_view = View()
                        for i, option in enumerate(poll["options"][:5]):
                            btn = Button(
                                label=option[:80],
                                emoji=OPTION_EMOJIS[i],
                                style=discord.ButtonStyle.secondary,
                                custom_id=f"poll_ended_{poll['id']}_{i}",
                                disabled=True
                            )
                            disabled_view.add_item(btn)
                        await msg.edit(embed=ended_embed, view=disabled_view)
                    except discord.NotFound:
                        pass

                # Post results
                await channel.send(embed=results_embed)
            except Exception as e:
                print(f"[Poll] Error ending poll #{poll.get('id')}: {e}")

    @check_polls.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    @check_polls.error
    async def check_error(self, error):
        self.check_polls.restart()

    async def restore_views(self):
        for poll in db_get_all_active_polls():
            try:
                ends_at = datetime.fromisoformat(str(poll["ends_at"]).replace("Z", "+00:00").replace(" ", "T"))
                if datetime.now(timezone.utc) < ends_at:
                    view = PollView(poll["id"], poll["options"])
                    if poll.get("message_id"):
                        self.bot.add_view(view, message_id=int(poll["message_id"]))
            except Exception:
                continue

    @app_commands.command(name="poll", description="Create a poll with up to 5 options")
    @app_commands.describe(
        question="The poll question",
        duration="How long the poll runs (e.g. 1h, 30m, 2h30m)",
        option1="Option 1",
        option2="Option 2",
        option3="Option 3 (optional)",
        option4="Option 4 (optional)",
        option5="Option 5 (optional)"
    )
    async def poll(
        self,
        interaction: discord.Interaction,
        question: str,
        duration: str,
        option1: str,
        option2: str,
        option3: str = None,
        option4: str = None,
        option5: str = None
    ):
        interval = parse_duration(duration)
        if not interval:
            return await interaction.response.send_message(
                "❌ Invalid duration. Use formats like `1h`, `30m`, `2h30m`.", ephemeral=True
            )
        if interval < 60:
            return await interaction.response.send_message(
                "❌ Minimum poll duration is 1 minute.", ephemeral=True
            )
        if interval > 604800:
            return await interaction.response.send_message(
                "❌ Maximum poll duration is 7 days.", ephemeral=True
            )

        options = [o for o in [option1, option2, option3, option4, option5] if o]
        ends_at = (datetime.now(timezone.utc) + timedelta(seconds=interval)).isoformat()

        try:
            record = db_create_poll(
                guild_id=interaction.guild.id,
                channel_id=interaction.channel.id,
                question=question,
                options=options,
                created_by=interaction.user.id,
                ends_at=ends_at
            )
        except Exception as e:
            return await interaction.response.send_message(f"❌ Failed to create poll: `{e}`", ephemeral=True)

        poll_id = record["id"]
        embed = build_poll_embed(record, [])
        view = PollView(poll_id, options)

        await interaction.response.send_message(embed=embed, view=view)
        msg = await interaction.original_response()
        db_set_message_id(poll_id, msg.id)
        self.bot.add_view(view, message_id=msg.id)

    @app_commands.command(name="endpoll", description="End a poll early and show results")
    @app_commands.describe(poll_id="The Poll ID to end (shown in poll footer)")
    async def endpoll(self, interaction: discord.Interaction, poll_id: int):
        poll = db_get_poll(poll_id)

        if not poll:
            return await interaction.response.send_message("❌ Poll not found.", ephemeral=True)
        if poll["guild_id"] != interaction.guild.id:
            return await interaction.response.send_message("❌ Poll not found.", ephemeral=True)
        if poll.get("ended"):
            return await interaction.response.send_message("⚠️ This poll has already ended.", ephemeral=True)
        if poll["created_by"] != interaction.user.id:
            # Check if staff
            staff_ids = []
            if not any(role.id in staff_ids for role in interaction.user.roles):
                if poll["created_by"] != interaction.user.id:
                    return await interaction.response.send_message(
                        "❌ Only the poll creator can end this poll early.", ephemeral=True
                    )

        await interaction.response.defer()
        db_mark_ended(poll_id)
        votes = db_get_votes(poll_id)

        # Edit original message
        if poll.get("message_id"):
            try:
                channel = interaction.guild.get_channel(int(poll["channel_id"]))
                if channel:
                    msg = await channel.fetch_message(int(poll["message_id"]))
                    ended_embed = build_poll_embed(poll, votes, ended=True)
                    disabled_view = View()
                    for i, option in enumerate(poll["options"][:5]):
                        btn = Button(
                            label=option[:80],
                            emoji=OPTION_EMOJIS[i],
                            style=discord.ButtonStyle.secondary,
                            custom_id=f"poll_ended_early_{poll_id}_{i}",
                            disabled=True
                        )
                        disabled_view.add_item(btn)
                    await msg.edit(embed=ended_embed, view=disabled_view)
            except discord.NotFound:
                pass

        results_embed = build_results_embed(poll, votes)
        await interaction.followup.send(embed=results_embed)


async def setup(bot):
    cog = Poll(bot)
    await bot.add_cog(cog)
    await cog.restore_views()
