import discord
from discord.ext import commands
from discord import app_commands

STAFF_ROLE_ID = 1389824693388837035

# Rank structure — order matters (lowest to highest)
RANKS = [
    {
        "name": "Trainee Pilot",
        "role_id": 1389826912351948840,
        "hours": "0–25 hours",
        "aircraft": "B38M / B737 / A220 / A319 / Dash 8Q400",
        "emoji": "🟠"
    },
    {
        "name": "Second Officer",
        "role_id": 1389830256751415346,
        "hours": "25–85 hours",
        "aircraft": "A321 / B738 / B379 / E175 / E190 / CRJ",
        "emoji": "🟠"
    },
    {
        "name": "First Officer",
        "role_id": 1389830388217680022,
        "hours": "85–190 hours",
        "aircraft": "B767 / B757 / A333 / A339",
        "emoji": "🟠"
    },
    {
        "name": "Senior First Officer",
        "role_id": 1389830625669939220,
        "hours": "190–300 hours",
        "aircraft": "B788 / B789 / B78X",
        "emoji": "🟡"
    },
    {
        "name": "Captain",
        "role_id": 1389830747455623219,
        "hours": "300–550 hours",
        "aircraft": "B77L / B77W / B772 / B744 / A346",
        "emoji": "🟡"
    },
    {
        "name": "Senior Captain",
        "role_id": 1389830897594798090,
        "hours": "550–700 hours",
        "aircraft": "A359 / B478",
        "emoji": "🟡"
    },
    {
        "name": "Chief Pilot",
        "role_id": 1389830983595065344,
        "hours": "700+ hours",
        "aircraft": "A380",
        "emoji": "⭐"
    }
]

RANK_ROLE_IDS = {r["role_id"] for r in RANKS}


def is_staff(member: discord.Member) -> bool:
    return any(role.id == STAFF_ROLE_ID for role in member.roles)


def get_current_rank(member: discord.Member):
    member_role_ids = {role.id for role in member.roles}
    # Return the highest rank the member currently holds
    for rank in reversed(RANKS):
        if rank["role_id"] in member_role_ids:
            return rank
    return None


def get_rank_by_id(role_id: int):
    return next((r for r in RANKS if r["role_id"] == role_id), None)


class RankSelect(discord.ui.Select):
    def __init__(self, member: discord.Member, promoted_by: discord.Member):
        self.member = member
        self.promoted_by = promoted_by

        options = [
            discord.SelectOption(
                label=rank["name"],
                description=f"{rank['hours']} • {rank['aircraft'][:50]}",
                emoji=rank["emoji"],
                value=str(rank["role_id"])
            )
            for rank in RANKS
        ]

        super().__init__(
            placeholder="Select the new rank...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff can promote members.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True, thinking=True)

        new_role_id = int(self.values[0])
        new_rank = get_rank_by_id(new_role_id)
        old_rank = get_current_rank(self.member)
        guild = interaction.guild

        new_role = guild.get_role(new_role_id)
        if not new_role:
            return await interaction.followup.send(
                "❌ Role not found. Check role IDs.", ephemeral=True
            )

        # Prevent promoting to the same rank
        if old_rank and old_rank["role_id"] == new_role_id:
            return await interaction.followup.send(
                f"⚠️ {self.member.mention} already holds **{old_rank['name']}**.",
                ephemeral=True
            )

        # Remove all other rank roles, assign new one
        roles_to_remove = [
            guild.get_role(rid)
            for rid in RANK_ROLE_IDS
            if rid != new_role_id and guild.get_role(rid) in self.member.roles
        ]

        try:
            if roles_to_remove:
                await self.member.remove_roles(*roles_to_remove, reason=f"Rank promotion by {interaction.user}")
            await self.member.add_roles(new_role, reason=f"Rank promotion by {interaction.user}")
        except discord.Forbidden:
            return await interaction.followup.send(
                "❌ I don't have permission to manage this member's roles.", ephemeral=True
            )
        except discord.HTTPException as e:
            return await interaction.followup.send(f"❌ Failed to update roles: {e}", ephemeral=True)

        # Build promotion embed (used in channel + DM)
        is_promotion = (
            old_rank is None or
            RANKS.index(new_rank) > RANKS.index(old_rank)
        )
        action = "🎉 Promoted" if is_promotion else "🔄 Rank Updated"

        channel_embed = discord.Embed(
            title=f"{action} — {self.member.display_name}",
            color=discord.Color.orange()
        )
        channel_embed.set_thumbnail(url=self.member.display_avatar.url)
        channel_embed.add_field(
            name="👤 Member",
            value=self.member.mention,
            inline=True
        )
        channel_embed.add_field(
            name="📋 Previous Rank",
            value=old_rank["name"] if old_rank else "None",
            inline=True
        )
        channel_embed.add_field(
            name="🏅 New Rank",
            value=f"**{new_rank['name']}**",
            inline=True
        )
        channel_embed.add_field(
            name="⏱️ Hours Required",
            value=new_rank["hours"],
            inline=True
        )
        channel_embed.add_field(
            name="✈️ Aircraft Unlocked",
            value=new_rank["aircraft"],
            inline=True
        )
        channel_embed.add_field(
            name="👮 Promoted By",
            value=interaction.user.mention,
            inline=True
        )
        channel_embed.set_footer(text="AkasaAirVirtual • Rank System")

        # DM the member
        dm_embed = discord.Embed(
            title=f"🎉 Congratulations, {self.member.display_name}!",
            description=(
                f"You have been **{'promoted' if is_promotion else 'updated'}** "
                f"in **Akasa Air Virtual**!"
            ),
            color=discord.Color.orange()
        )
        dm_embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
        dm_embed.add_field(
            name="🏅 Your New Rank",
            value=f"**{new_rank['name']}**",
            inline=True
        )
        dm_embed.add_field(
            name="⏱️ Hours Required",
            value=new_rank["hours"],
            inline=True
        )
        dm_embed.add_field(
            name="✈️ Aircraft Now Unlocked",
            value=new_rank["aircraft"],
            inline=False
        )
        if old_rank:
            dm_embed.add_field(
                name="📋 Previous Rank",
                value=old_rank["name"],
                inline=True
            )
        dm_embed.add_field(
            name="👮 Promoted By",
            value=interaction.user.display_name,
            inline=True
        )
        dm_embed.set_footer(text="Keep up the great work! ✈️ — Akasa Air Virtual")

        dm_sent = True
        try:
            await self.member.send(embed=dm_embed)
        except discord.Forbidden:
            dm_sent = False

        # Confirm to staff
        confirm = f"✅ {self.member.mention} has been promoted to **{new_rank['name']}**."
        if not dm_sent:
            confirm += "\n⚠️ Could not send DM — their DMs may be closed."

        await interaction.followup.send(embed=channel_embed)
        await interaction.followup.send(confirm, ephemeral=True)


class RankPromotionView(discord.ui.View):
    def __init__(self, member: discord.Member, promoted_by: discord.Member):
        super().__init__(timeout=120)
        self.add_item(RankSelect(member, promoted_by))


class RankPromotion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="promote",
        description="Promote a member to a new rank (staff only)"
    )
    @app_commands.describe(member="The member to promote")
    async def promote(self, interaction: discord.Interaction, member: discord.Member):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff members can use this command.", ephemeral=True
            )

        if member.bot:
            return await interaction.response.send_message(
                "❌ You cannot promote a bot.", ephemeral=True
            )

        if member.id == interaction.user.id:
            return await interaction.response.send_message(
                "❌ You cannot promote yourself.", ephemeral=True
            )

        current_rank = get_current_rank(member)

        embed = discord.Embed(
            title=f"✈️ Promote — {member.display_name}",
            description=f"Select the new rank for {member.mention} from the dropdown below.",
            color=discord.Color.orange()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(
            name="📋 Current Rank",
            value=current_rank["name"] if current_rank else "No rank assigned",
            inline=True
        )
        embed.add_field(name="👤 Member", value=member.mention, inline=True)
        embed.set_footer(text="AkasaAirVirtual • Rank System")

        await interaction.response.send_message(
            embed=embed,
            view=RankPromotionView(member, interaction.user),
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(RankPromotion(bot))
