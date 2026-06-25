import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import os

STAFF_ROLE_ID = 1389824693388837035
DB_PATH = os.path.join(os.path.dirname(__file__), "callsigns.db")

# Same caveat as other cogs: if Railway does not have a persistent volume
# mounted, this DB file will be wiped on every redeploy. Attach a Railway
# volume or migrate to Supabase if you need true long-term persistence.


# ================= DATABASE =================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS callsigns (
            callsign TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            assigned_by INTEGER NOT NULL,
            assigned_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def db_get_callsign_by_number(callsign: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM callsigns WHERE callsign = ?", (callsign,)).fetchone()
    conn.close()
    return row


def db_get_callsign_by_user(user_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM callsigns WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row


def db_assign(callsign: str, user_id: int, assigned_by: int):
    conn = get_db()
    conn.execute(
        "INSERT INTO callsigns (callsign, user_id, assigned_by) VALUES (?, ?, ?)",
        (callsign, user_id, assigned_by)
    )
    conn.commit()
    conn.close()


def db_remove_by_user(user_id: int):
    conn = get_db()
    row = conn.execute("SELECT callsign FROM callsigns WHERE user_id = ?", (user_id,)).fetchone()
    if row:
        conn.execute("DELETE FROM callsigns WHERE user_id = ?", (user_id,))
        conn.commit()
    conn.close()
    return row["callsign"] if row else None


def db_remove_by_callsign(callsign: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM callsigns WHERE callsign = ?", (callsign,)).fetchone()
    if row:
        conn.execute("DELETE FROM callsigns WHERE callsign = ?", (callsign,))
        conn.commit()
    conn.close()
    return row


def db_get_range(start: int, end: int):
    taken = {}
    conn = get_db()
    rows = conn.execute("SELECT callsign, user_id FROM callsigns").fetchall()
    conn.close()
    for row in rows:
        taken[row["callsign"]] = row["user_id"]
    return taken


def db_transfer(callsign: str, new_user_id: int, transferred_by: int):
    conn = get_db()
    conn.execute(
        "UPDATE callsigns SET user_id = ?, assigned_by = ?, assigned_at = datetime('now') WHERE callsign = ?",
        (new_user_id, transferred_by, callsign)
    )
    conn.commit()
    conn.close()


def db_total_assigned():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM callsigns").fetchone()[0]
    conn.close()
    return count


def is_staff(member: discord.Member) -> bool:
    return any(role.id == STAFF_ROLE_ID for role in member.roles)


def validate_number(number: int) -> bool:
    return 100 <= number <= 999


# ================= COG =================

class Callsign(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        init_db()

    # ================= CHECK CALLSIGN =================

    @app_commands.command(name="check_callsign", description="Check if a callsign number is available")
    @app_commands.describe(number="Callsign number (100-999)")
    async def check_callsign(self, interaction: discord.Interaction, number: int):
        if not validate_number(number):
            return await interaction.response.send_message(
                "❌ Number must be between 100 and 999.", ephemeral=True
            )

        cs = f"{number}QP"
        row = db_get_callsign_by_number(cs)

        if row:
            member = interaction.guild.get_member(row["user_id"])
            mention = member.mention if member else f"<@{row['user_id']}>"
            await interaction.response.send_message(
                f"❌ **{cs}** is taken by {mention}.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"✅ **{cs}** is available!", ephemeral=True
            )

    # ================= MY CALLSIGN =================

    @app_commands.command(name="my_callsign", description="Check your own assigned callsign")
    async def my_callsign(self, interaction: discord.Interaction):
        row = db_get_callsign_by_user(interaction.user.id)

        if not row:
            return await interaction.response.send_message(
                "⚠️ You don't have an assigned callsign yet. Contact staff to get one.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="✈️ Your Callsign",
            color=discord.Color.orange()
        )
        embed.add_field(name="Callsign", value=f"**{row['callsign']}**", inline=True)
        embed.add_field(name="Assigned At", value=row["assigned_at"][:10], inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ================= CALLSIGN LIST =================

    @app_commands.command(name="callsign_list", description="View callsign availability for a number range")
    @app_commands.describe(start="Start of range (100-999)", end="End of range (100-999)")
    async def callsign_list(self, interaction: discord.Interaction, start: int, end: int):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Staff only.", ephemeral=True)

        if not validate_number(start) or not validate_number(end) or start > end:
            return await interaction.response.send_message(
                "❌ Use a valid range between 100 and 999.", ephemeral=True
            )

        if end - start > 99:
            return await interaction.response.send_message(
                "❌ Range too large. Max 100 at a time.", ephemeral=True
            )

        taken = db_get_range(start, end)
        lines = []

        for i in range(start, end + 1):
            cs = f"{i}QP"
            if cs in taken:
                member = interaction.guild.get_member(taken[cs])
                name = member.display_name if member else f"ID:{taken[cs]}"
                lines.append(f"🔴 `{cs}` — {name}")
            else:
                lines.append(f"🟢 `{cs}` — Available")

        chunks = [lines[i:i+30] for i in range(0, len(lines), 30)]
        total_taken = sum(1 for i in range(start, end+1) if f"{i}QP" in taken)
        total_available = (end - start + 1) - total_taken

        await interaction.response.send_message(
            f"📋 **Callsigns {start}QP–{end}QP** | 🔴 {total_taken} taken · 🟢 {total_available} available",
            ephemeral=True
        )

        for idx, chunk in enumerate(chunks):
            await interaction.followup.send(
                f"```\n" + "\n".join(chunk) + "\n```",
                ephemeral=True
            )

    # ================= ASSIGN CALLSIGN =================

    @app_commands.command(name="assign_callsign", description="Assign a callsign to a member")
    @app_commands.describe(member="The member to assign to", number="Callsign number (100-999)")
    async def assign_callsign(self, interaction: discord.Interaction, member: discord.Member, number: int):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Staff only.", ephemeral=True)

        if not validate_number(number):
            return await interaction.response.send_message(
                "❌ Number must be between 100 and 999.", ephemeral=True
            )

        cs = f"{number}QP"

        # Check if callsign is already taken
        existing = db_get_callsign_by_number(cs)
        if existing:
            taken_member = interaction.guild.get_member(existing["user_id"])
            mention = taken_member.mention if taken_member else f"<@{existing['user_id']}>"
            return await interaction.response.send_message(
                f"❌ **{cs}** is already assigned to {mention}.", ephemeral=True
            )

        # Check if member already has a callsign
        current = db_get_callsign_by_user(member.id)
        if current:
            return await interaction.response.send_message(
                f"⚠️ {member.mention} already has **{current['callsign']}**. "
                f"Remove it first with `/remove_callsign`.",
                ephemeral=True
            )

        db_assign(cs, member.id, interaction.user.id)

        embed = discord.Embed(
            title="✅ Callsign Assigned",
            color=discord.Color.green()
        )
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="Callsign", value=f"**{cs}**", inline=True)
        embed.add_field(name="Assigned By", value=interaction.user.mention, inline=True)

        await interaction.response.send_message(embed=embed)

    # ================= REMOVE CALLSIGN =================

    @app_commands.command(name="remove_callsign", description="Remove a member's callsign")
    @app_commands.describe(member="The member to remove the callsign from")
    async def remove_callsign(self, interaction: discord.Interaction, member: discord.Member):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Staff only.", ephemeral=True)

        removed_cs = db_remove_by_user(member.id)

        if not removed_cs:
            return await interaction.response.send_message(
                f"⚠️ {member.mention} has no assigned callsign.", ephemeral=True
            )

        embed = discord.Embed(
            title="🗑️ Callsign Removed",
            color=discord.Color.red()
        )
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="Callsign", value=f"**{removed_cs}**", inline=True)
        embed.add_field(name="Removed By", value=interaction.user.mention, inline=True)

        await interaction.response.send_message(embed=embed)

    # ================= TRANSFER CALLSIGN =================

    @app_commands.command(name="transfer_callsign", description="Transfer a callsign from one member to another")
    @app_commands.describe(callsign_number="The callsign number to transfer", to_member="The member to transfer it to")
    async def transfer_callsign(self, interaction: discord.Interaction, callsign_number: int, to_member: discord.Member):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Staff only.", ephemeral=True)

        if not validate_number(callsign_number):
            return await interaction.response.send_message(
                "❌ Number must be between 100 and 999.", ephemeral=True
            )

        cs = f"{callsign_number}QP"
        row = db_get_callsign_by_number(cs)

        if not row:
            return await interaction.response.send_message(
                f"⚠️ **{cs}** is not currently assigned.", ephemeral=True
            )

        # Check target doesn't already have a callsign
        current = db_get_callsign_by_user(to_member.id)
        if current:
            return await interaction.response.send_message(
                f"⚠️ {to_member.mention} already has **{current['callsign']}**. Remove it first.",
                ephemeral=True
            )

        old_member = interaction.guild.get_member(row["user_id"])
        old_mention = old_member.mention if old_member else f"<@{row['user_id']}>"

        db_transfer(cs, to_member.id, interaction.user.id)

        embed = discord.Embed(
            title="🔄 Callsign Transferred",
            color=discord.Color.blue()
        )
        embed.add_field(name="Callsign", value=f"**{cs}**", inline=True)
        embed.add_field(name="From", value=old_mention, inline=True)
        embed.add_field(name="To", value=to_member.mention, inline=True)
        embed.add_field(name="By", value=interaction.user.mention, inline=True)

        await interaction.response.send_message(embed=embed)

    # ================= CALLSIGN STATS =================

    @app_commands.command(name="callsign_stats", description="View callsign assignment statistics")
    async def callsign_stats(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Staff only.", ephemeral=True)

        total_assigned = db_total_assigned()
        total_available = 900 - total_assigned  # 100-999 = 900 slots

        embed = discord.Embed(
            title="📊 Callsign Statistics",
            color=discord.Color.orange()
        )
        embed.add_field(name="🔴 Assigned", value=str(total_assigned), inline=True)
        embed.add_field(name="🟢 Available", value=str(total_available), inline=True)
        embed.add_field(name="📋 Total Slots", value="900 (100QP–999QP)", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ================= WHOIS CALLSIGN =================

    @app_commands.command(name="whois_callsign", description="Look up who owns a specific callsign")
    @app_commands.describe(number="Callsign number (100-999)")
    async def whois_callsign(self, interaction: discord.Interaction, number: int):
        if not validate_number(number):
            return await interaction.response.send_message(
                "❌ Number must be between 100 and 999.", ephemeral=True
            )

        cs = f"{number}QP"
        row = db_get_callsign_by_number(cs)

        if not row:
            return await interaction.response.send_message(
                f"✅ **{cs}** is not assigned to anyone.", ephemeral=True
            )

        member = interaction.guild.get_member(row["user_id"])
        mention = member.mention if member else f"<@{row['user_id']}>"
        assigned_by = interaction.guild.get_member(row["assigned_by"])
        by_mention = assigned_by.mention if assigned_by else f"<@{row['assigned_by']}>"

        embed = discord.Embed(title=f"🔍 Callsign Lookup — {cs}", color=discord.Color.orange())
        embed.add_field(name="Assigned To", value=mention, inline=True)
        embed.add_field(name="Assigned By", value=by_mention, inline=True)
        embed.add_field(name="Date", value=row["assigned_at"][:10], inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Callsign(bot))
