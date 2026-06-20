import discord
from discord.ext import commands
from discord import app_commands

STAFF_ROLE = 1389824693388837035

ROLE_OPTIONS = [
    {
        "label": "Group Flights",
        "description": "Get pinged when someone is looking to fly together",
        "emoji": "✈️",
        "role_id": 1432617344068227102
    },
    {
        "label": "Featured",
        "description": "Be the first to see pilot spotlights, top screenshots, and VA highlights",
        "emoji": "🗺️",
        "role_id": 1432617094956060683
    },
    {
        "label": "Announcements",
        "description": "Get notified when we post official news or updates",
        "emoji": "📢",
        "role_id": 1432617170801791049
    },
    {
        "label": "IFATC Member",
        "description": "Select this if you're part of IFATC",
        "emoji": "<:IFATC:1389866636118462494>",
        "role_id": 1389833550957641840
    },
    {
        "label": "IFAET Member",
        "description": "Choose this if you're part of IFAET",
        "emoji": "<:IFAET:1389866639805255733>",
        "role_id": 1389833738128719883
    }
]


def is_staff(member):
    return STAFF_ROLE in [role.id for role in member.roles]


class SelfRoleSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=opt["label"],
                description=opt["description"],
                emoji=opt["emoji"],
                value=str(opt["role_id"])
            )
            for opt in ROLE_OPTIONS
        ]

        super().__init__(
            placeholder="🌀 Select your notification role",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="self_role_select"
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user

        selected_id = int(self.values[0])
        selected_opt = next((opt for opt in ROLE_OPTIONS if opt["role_id"] == selected_id), None)

        if not selected_opt:
            await interaction.response.send_message("⚠️ Unknown role selected.", ephemeral=True)
            return

        role = guild.get_role(selected_id)
        if not role:
            await interaction.response.send_message("⚠️ That role no longer exists.", ephemeral=True)
            return

        if role in member.roles:
            await member.remove_roles(role, reason="Self-role panel deselection")
            await interaction.response.send_message(
                f"❌ Removed: **{selected_opt['label']}**", ephemeral=True
            )
        else:
            await member.add_roles(role, reason="Self-role panel selection")
            await interaction.response.send_message(
                f"✅ Added: **{selected_opt['label']}**", ephemeral=True
            )


class SelfRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(SelfRoleSelect())


class SelfRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="rolepanel", description="Send the self-roles selection panel")
    async def rolepanel(self, interaction: discord.Interaction, channel: discord.TextChannel):

        if not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Only staff members can send the role panel.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="Self Roles",
            description=(
                "## Self Roles\n\n"
                "Hey there! Want to stay in the loop with everything happening at "
                "**Akasa Air Virtual**? Pick your notification roles below so you only "
                "get updates that matter to you. Choose one, a few, or all — it's totally "
                "your call!\n\n"
                "✈️ **Group Flights** – Get pinged when someone is looking to fly together.\n"
                "🗺️ **Featured** – Be the first to see pilot spotlights, top screenshots, "
                "and VA highlights.\n"
                "📢 **Announcements** – Get notified when we post official news or updates.\n"
                "<:IFATC:1389866636118462494> **IFATC Member** – Select this if you're part of IFATC.\n"
                "<:IFAET:1389866639805255733> **IFAET Member** – Choose this if you're part of IFAET."
            ),
            color=discord.Color.orange()
        )
        embed.set_footer(text="Akasa Air Virtual")

        await channel.send(embed=embed, view=SelfRoleView())

        await interaction.response.send_message(
            f"✅ Role panel sent in {channel.mention}",
            ephemeral=True
        )


# Mandatory setup function
async def setup(bot):
    await bot.add_cog(SelfRoles(bot))
    bot.add_view(SelfRoleView())
