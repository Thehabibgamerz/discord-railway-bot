import discord
from discord.ext import commands
from discord import app_commands
from supabase import create_client, Client
import os

STAFF_ROLE_ID = 1389824693388837035

SUPABASE_URL = "https://xljanwcgesjhdoaavmuo.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


def get_db() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def is_staff(member: discord.Member) -> bool:
    return any(role.id == STAFF_ROLE_ID for role in member.roles)


def validate_number(number: int) -> bool:
    return 100 <= number <= 999


# ================= DATABASE HELPERS =================

def db_get_callsign_by_number(callsign: str):
    try:
        res = get_db().table("callsigns").select("*").eq("callsign", callsign).single().execute()
        return res.data
    except Exception:
        return None


def db_get_callsign_by_user(user_id: int):
    try:
        res = get_db().table("callsigns").select("*").eq("user_id", user_id).single().execute()
        return res.data
    except Exception:
        return None


def db_assign(callsign: str, user_id: int, assigned_by: int):
    get_db().table("callsigns").insert({
        "callsign": callsign,
        "user_id": user_id,
        "assigned_by": assigned_by
    }).execute()


def db_remove_by_user(user_id: int):
    existing = db_get_callsign_by_user(user_id)
    if not existing:
        return None
    get_db().table("callsigns").delete().eq("user_id", user_id).execute()
    return existing["callsign"]


def db_get_all():
    try:
        res = get_db().table("callsigns").select("callsign, user_id").execute()
        return {row["callsign"]: row["user_id"] for row in res.data}
    except Exception:
        return {}


def db_transfer(callsign: str, new_user_id: int, transferred_by: int):
    get_db().table("callsigns").update({
        "user_id": new_user_id,
        "assigned_by": transferred_by
    }).eq("callsign", callsign).execute()


def db_total_assigned():
    try:
        res = get_db().table("callsigns").select("callsign", count="exact").execute()
        return res.count or 0
    except Exception:
        return 0


# ================= COG =================

class Callsign(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

        embed = discord.Embed(title="✈️ Your Callsign", color=discord.Color.orange())
        embed.add_field(name="Callsign", value=f"**{row['callsign']}**", inline=True)
        embed.add_field(name="Assigned At", value=str(row["assigned_at"])[:10], inline=True)

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

        taken = db_get_all()
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
        total_taken = sum(1 for i in range(start, end + 1) if f"{i}QP" in taken)
        total_available = (end - start + 1) - total_taken

        await interaction.response.send_message(
            f"📋 **Callsigns {start}QP–{end}QP** | 🔴 {total_taken} taken · 🟢 {total_available} available",
            ephemeral=True
        )

        for chunk in chunks:
            await interaction.followup.send(
                "```\n" + "\n".join(chunk) + "\n```",
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

        existing = db_get_callsign_by_number(cs)
        if existing:
            taken_member = interaction.guild.get_member(existing["user_id"])
            mention = taken_member.mention if taken_member else f"<@{existing['user_id']}>"
            return await interaction.response.send_message(
                f"❌ **{cs}** is already assigned to {mention}.", ephemeral=True
            )

        current = db_get_callsign_by_user(member.id)
        if current:
            return await interaction.response.send_message(
                f"⚠️ {member.mention} already has **{current['callsign']}**. "
                f"Remove it first with `/remove_callsign`.",
                ephemeral=True
            )

        db_assign(cs, member.id, interaction.user.id)

        embed = discord.Embed(title="✅ Callsign Assigned", color=discord.Color.green())
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

        embed = discord.Embed(title="🗑️ Callsign Removed", color=discord.Color.red())
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

        current = db_get_callsign_by_user(to_member.id)
        if current:
            return await interaction.response.send_message(
                f"⚠️ {to_member.mention} already has **{current['callsign']}**. Remove it first.",
                ephemeral=True
            )

        old_member = interaction.guild.get_member(row["user_id"])
        old_mention = old_member.mention if old_member else f"<@{row['user_id']}>"

        db_transfer(cs, to_member.id, interaction.user.id)

        embed = discord.Embed(title="🔄 Callsign Transferred", color=discord.Color.blue())
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
        total_available = 900 - total_assigned

        embed = discord.Embed(title="📊 Callsign Statistics", color=discord.Color.orange())
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
        embed.add_field(name="Date", value=str(row["assigned_at"])[:10], inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Callsign(bot))
