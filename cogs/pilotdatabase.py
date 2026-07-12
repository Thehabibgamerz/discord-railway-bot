import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
from supabase import create_client, Client
from datetime import datetime, timezone
import os

EXEC_ROLE_ID = 1389824452778262589

SUPABASE_URL = "https://xljanwcgesjhdoaavmuo.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


def get_db() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def is_exec(member: discord.Member) -> bool:
    return any(role.id == EXEC_ROLE_ID for role in member.roles)


# ================= SUPABASE HELPERS =================

def db_add_pilot(discord_id: int, callsign: str, rank: str, ifc_username: str, join_date: str, status: str):
    get_db().table("pilot_database").insert({
        "discord_id": discord_id,
        "callsign": callsign.upper(),
        "rank": rank,
        "ifc_username": ifc_username,
        "join_date": join_date,
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat()
    }).execute()


def db_get_pilot_by_callsign(callsign: str):
    try:
        res = get_db().table("pilot_database").select("*").eq("callsign", callsign.upper()).single().execute()
        return res.data
    except Exception:
        return None


def db_get_pilot_by_ifc(ifc_username: str):
    try:
        res = get_db().table("pilot_database").select("*").ilike("ifc_username", ifc_username).execute()
        return res.data or []
    except Exception:
        return []


def db_update_pilot(callsign: str, updates: dict):
    get_db().table("pilot_database").update(updates).eq("callsign", callsign.upper()).execute()


def db_delete_pilot(callsign: str):
    get_db().table("pilot_database").delete().eq("callsign", callsign.upper()).execute()


def db_get_all_pilots():
    try:
        res = get_db().table("pilot_database").select("*").order("callsign").execute()
        return res.data or []
    except Exception:
        return []


# ================= PILOT EMBED =================

def build_pilot_embed(pilot: dict, guild: discord.Guild) -> discord.Embed:
    status = pilot.get("status", "Active")
    color = discord.Color.green() if status == "Active" else discord.Color.red()
    member = guild.get_member(int(pilot.get("discord_id", 0)))
    mention = member.mention if member else f"<@{pilot['discord_id']}>"

    embed = discord.Embed(
        title=f"✈️ Pilot Record — {pilot.get('callsign', 'N/A')}",
        color=color
    )
    embed.add_field(name="👤 Discord", value=mention, inline=True)
    embed.add_field(name="🪪 Callsign", value=f"**{pilot.get('callsign', 'N/A')}**", inline=True)
    embed.add_field(name="🏅 Rank", value=pilot.get("rank", "N/A"), inline=True)
    embed.add_field(name="🌐 IFC Username", value=pilot.get("ifc_username", "N/A"), inline=True)
    embed.add_field(name="📅 Join Date", value=pilot.get("join_date", "N/A"), inline=True)
    embed.add_field(
        name="📊 Status",
        value="🟢 Active" if status == "Active" else "🔴 Inactive",
        inline=True
    )
    embed.set_footer(text="AkasaAirVirtual • Pilot Database")
    if member:
        embed.set_thumbnail(url=member.display_avatar.url)
    return embed


# ================= MODALS =================

class AddPilotModal(Modal):
    def __init__(self):
        super().__init__(title="Add Pilot to Database")
        self.discord_id_field = TextInput(label="Discord User ID", placeholder="e.g. 123456789012345678", max_length=20)
        self.callsign = TextInput(label="Callsign", placeholder="e.g. 201QP", max_length=10)
        self.rank = TextInput(label="Rank", placeholder="e.g. Trainee Pilot", max_length=30)
        self.ifc_username = TextInput(label="IFC Username", placeholder="Infinite Flight Community username", max_length=50)
        self.join_date = TextInput(label="Join Date", placeholder="e.g. 2024-07-11", max_length=20)
        self.add_item(self.discord_id_field)
        self.add_item(self.callsign)
        self.add_item(self.rank)
        self.add_item(self.ifc_username)
        self.add_item(self.join_date)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            discord_id = int(self.discord_id_field.value.strip())
        except ValueError:
            return await interaction.response.send_message(
                "❌ Invalid Discord User ID — must be a number.", ephemeral=True
            )

        callsign = self.callsign.value.strip().upper()
        existing = db_get_pilot_by_callsign(callsign)
        if existing:
            return await interaction.response.send_message(
                f"❌ A pilot with callsign **{callsign}** already exists.", ephemeral=True
            )

        db_add_pilot(
            discord_id=discord_id,
            callsign=callsign,
            rank=self.rank.value.strip(),
            ifc_username=self.ifc_username.value.strip(),
            join_date=self.join_date.value.strip(),
            status="Active"
        )

        embed = discord.Embed(
            title="✅ Pilot Added",
            color=discord.Color.green()
        )
        embed.add_field(name="👤 Discord", value=f"<@{discord_id}>", inline=True)
        embed.add_field(name="🪪 Callsign", value=callsign, inline=True)
        embed.add_field(name="🏅 Rank", value=self.rank.value.strip(), inline=True)
        embed.add_field(name="🌐 IFC", value=self.ifc_username.value.strip(), inline=True)
        embed.add_field(name="📅 Join Date", value=self.join_date.value.strip(), inline=True)
        embed.add_field(name="📊 Status", value="🟢 Active", inline=True)
        embed.set_footer(text="AkasaAirVirtual • Pilot Database")
        await interaction.response.send_message(embed=embed)


class SearchPilotModal(Modal):
    def __init__(self):
        super().__init__(title="Search Pilot Database")
        self.query = TextInput(
            label="Callsign or IFC Username",
            placeholder="e.g. 201QP or TheHabib_Gamerz",
            max_length=50
        )
        self.add_item(self.query)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        query = self.query.value.strip()
        pilot = db_get_pilot_by_callsign(query)
        if not pilot:
            results = db_get_pilot_by_ifc(query)
            pilot = results[0] if results else None

        if not pilot:
            return await interaction.followup.send(
                f"⚠️ No pilot found matching **{query}**.", ephemeral=True
            )

        embed = build_pilot_embed(pilot, interaction.guild)
        await interaction.followup.send(embed=embed, ephemeral=True)


class EditPilotModal(Modal):
    def __init__(self):
        super().__init__(title="Edit Pilot Record")
        self.callsign = TextInput(label="Callsign to Edit", placeholder="e.g. 201QP", max_length=10)
        self.new_rank = TextInput(label="New Rank (blank = keep current)", required=False, max_length=30)
        self.new_ifc = TextInput(label="New IFC Username (blank = keep current)", required=False, max_length=50)
        self.new_status = TextInput(label="New Status: Active or Inactive (blank = keep)", required=False, max_length=10)
        self.new_join_date = TextInput(label="New Join Date (blank = keep current)", required=False, max_length=20)
        self.add_item(self.callsign)
        self.add_item(self.new_rank)
        self.add_item(self.new_ifc)
        self.add_item(self.new_status)
        self.add_item(self.new_join_date)

    async def on_submit(self, interaction: discord.Interaction):
        callsign = self.callsign.value.strip().upper()
        pilot = db_get_pilot_by_callsign(callsign)
        if not pilot:
            return await interaction.response.send_message(
                f"⚠️ No pilot found with callsign **{callsign}**.", ephemeral=True
            )

        updates = {}
        if self.new_rank.value.strip():
            updates["rank"] = self.new_rank.value.strip()
        if self.new_ifc.value.strip():
            updates["ifc_username"] = self.new_ifc.value.strip()
        if self.new_status.value.strip() in ("Active", "Inactive"):
            updates["status"] = self.new_status.value.strip()
        if self.new_join_date.value.strip():
            updates["join_date"] = self.new_join_date.value.strip()

        if not updates:
            return await interaction.response.send_message(
                "⚠️ No changes made — all fields were blank.", ephemeral=True
            )

        db_update_pilot(callsign, updates)
        updated = db_get_pilot_by_callsign(callsign)
        embed = build_pilot_embed(updated, interaction.guild)
        embed.title = f"✏️ Pilot Updated — {callsign}"
        await interaction.response.send_message(embed=embed)


class DeletePilotModal(Modal):
    def __init__(self):
        super().__init__(title="Remove Pilot from Database")
        self.callsign = TextInput(label="Callsign to Remove", placeholder="e.g. 201QP", max_length=10)
        self.confirm = TextInput(label="Type CONFIRM to proceed", placeholder="CONFIRM", max_length=10)
        self.add_item(self.callsign)
        self.add_item(self.confirm)

    async def on_submit(self, interaction: discord.Interaction):
        if self.confirm.value.strip() != "CONFIRM":
            return await interaction.response.send_message(
                "❌ Removal cancelled — you must type **CONFIRM** exactly.", ephemeral=True
            )
        callsign = self.callsign.value.strip().upper()
        pilot = db_get_pilot_by_callsign(callsign)
        if not pilot:
            return await interaction.response.send_message(
                f"⚠️ No pilot found with callsign **{callsign}**.", ephemeral=True
            )
        db_delete_pilot(callsign)
        await interaction.response.send_message(
            f"🗑️ Pilot **{callsign}** has been removed from the database.", ephemeral=True
        )


# ================= PANEL VIEW =================

class PilotDatabaseView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def check_exec(self, interaction: discord.Interaction) -> bool:
        if not is_exec(interaction.user):
            await interaction.response.send_message(
                "❌ Only the Executive Team can use this panel.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Add Pilot", emoji="➕", style=discord.ButtonStyle.success, custom_id="pilotdb_add")
    async def add_pilot(self, interaction: discord.Interaction, button: Button):
        if not await self.check_exec(interaction):
            return
        await interaction.response.send_modal(AddPilotModal())

    @discord.ui.button(label="Search Pilot", emoji="🔍", style=discord.ButtonStyle.primary, custom_id="pilotdb_search")
    async def search_pilot(self, interaction: discord.Interaction, button: Button):
        if not await self.check_exec(interaction):
            return
        await interaction.response.send_modal(SearchPilotModal())

    @discord.ui.button(label="Edit Pilot", emoji="✏️", style=discord.ButtonStyle.secondary, custom_id="pilotdb_edit")
    async def edit_pilot(self, interaction: discord.Interaction, button: Button):
        if not await self.check_exec(interaction):
            return
        await interaction.response.send_modal(EditPilotModal())

    @discord.ui.button(label="Remove Pilot", emoji="🗑️", style=discord.ButtonStyle.danger, custom_id="pilotdb_delete")
    async def delete_pilot(self, interaction: discord.Interaction, button: Button):
        if not await self.check_exec(interaction):
            return
        await interaction.response.send_modal(DeletePilotModal())

    @discord.ui.button(label="View All Pilots", emoji="📋", style=discord.ButtonStyle.secondary, custom_id="pilotdb_viewall")
    async def view_all(self, interaction: discord.Interaction, button: Button):
        if not await self.check_exec(interaction):
            return

        await interaction.response.defer(ephemeral=True)
        pilots = db_get_all_pilots()

        if not pilots:
            return await interaction.followup.send(
                "⚠️ No pilots in the database yet.", ephemeral=True
            )

        active = [p for p in pilots if p.get("status") == "Active"]
        inactive = [p for p in pilots if p.get("status") == "Inactive"]

        embed = discord.Embed(
            title="📋 Pilot Database — Full Roster",
            description=f"**Total:** {len(pilots)} · 🟢 Active: {len(active)} · 🔴 Inactive: {len(inactive)}",
            color=discord.Color.orange()
        )

        if active:
            lines = []
            for p in active[:20]:
                member = interaction.guild.get_member(int(p.get("discord_id", 0)))
                name = member.display_name if member else f"<@{p['discord_id']}>"
                lines.append(f"• **{p['callsign']}** — {name} · {p.get('rank', 'N/A')}")
            embed.add_field(
                name=f"🟢 Active ({len(active)})",
                value="\n".join(lines) + ("\n*...and more*" if len(active) > 20 else ""),
                inline=False
            )

        if inactive:
            lines = []
            for p in inactive[:10]:
                member = interaction.guild.get_member(int(p.get("discord_id", 0)))
                name = member.display_name if member else f"<@{p['discord_id']}>"
                lines.append(f"• **{p['callsign']}** — {name} · {p.get('rank', 'N/A')}")
            embed.add_field(
                name=f"🔴 Inactive ({len(inactive)})",
                value="\n".join(lines) + ("\n*...and more*" if len(inactive) > 10 else ""),
                inline=False
            )

        embed.set_footer(text="AkasaAirVirtual • Pilot Database")
        await interaction.followup.send(embed=embed, ephemeral=True)


# ================= COG =================

class PilotDatabase(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="pilotdatabase_panel", description="Send the Pilot Database panel (Executive Team only)")
    @app_commands.describe(channel="Channel to post the panel in")
    async def pilotdatabase_panel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_exec(interaction.user):
            return await interaction.response.send_message(
                "❌ Only the Executive Team can send the pilot database panel.", ephemeral=True
            )

        embed = discord.Embed(
            title="🗂️ Akasa Air Virtual — Pilot Database",
            description=(
                "Welcome to the official **Pilot Database** management panel.\n\n"
                "➕ **Add Pilot** — Register a new pilot record\n"
                "🔍 **Search Pilot** — Find a pilot by callsign or IFC username\n"
                "✏️ **Edit Pilot** — Update an existing pilot's details\n"
                "🗑️ **Remove Pilot** — Remove a pilot from the database\n"
                "📋 **View All Pilots** — Browse the full active roster\n\n"
                "*Access restricted to Executive Team only.*"
            ),
            color=discord.Color.orange()
        )
        embed.set_footer(text="AkasaAirVirtual • Pilot Database")

        view = PilotDatabaseView()
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            f"✅ Pilot Database panel sent in {channel.mention}", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(PilotDatabase(bot))
    bot.add_view(PilotDatabaseView())
