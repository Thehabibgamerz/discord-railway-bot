import discord
from discord.ext import commands
from discord import app_commands

# 🔁 UPDATED ROLE IDS
STAFF_ROLE_ID = 1389824693388837035

GROUP_ROLE = 1432617344068227102
FEATURED_ROLE = 1432617094956060683
ANNOUNCE_ROLE = 1432617170801791049
IFATC_ROLE = 1389833550957641840
IFAET_ROLE = 1389833738128719883


# ================= VIEW =================

class SelfRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def toggle_role(self, interaction: discord.Interaction, role_id: int):

        role = interaction.guild.get_role(role_id)

        if not role:
            return await interaction.response.send_message("❌ Role not found", ephemeral=True)

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"❌ Removed {role.name}", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Added {role.name}", ephemeral=True)

    # BUTTONS

    @discord.ui.button(label="Group Flights", emoji="🛫", style=discord.ButtonStyle.secondary, custom_id="role_group")
    async def group(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, GROUP_ROLE)

    @discord.ui.button(label="Featured", emoji="🗺️", style=discord.ButtonStyle.secondary, custom_id="role_featured")
    async def featured(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, FEATURED_ROLE)

    @discord.ui.button(label="Announcements", emoji="📣", style=discord.ButtonStyle.secondary, custom_id="role_announce")
    async def announce(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, ANNOUNCE_ROLE)

    @discord.ui.button(label="IFATC Member", emoji="✈️", style=discord.ButtonStyle.success, custom_id="role_ifatc")
    async def ifatc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, IFATC_ROLE)

    @discord.ui.button(label="IFAET Member", emoji="🛠️", style=discord.ButtonStyle.success, custom_id="role_ifaet")
    async def ifaet(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.toggle_role(interaction, IFAET_ROLE)


# ================= COG =================

class SelfRoles(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="reaction_role", description="Send self role panel")
    async def reaction_role(self, interaction: discord.Interaction, channel: discord.TextChannel):

        # ✅ STAFF ONLY
        if STAFF_ROLE_ID not in [r.id for r in interaction.user.roles]:
            return await interaction.response.send_message("❌ Staff only command", ephemeral=True)

        embed = discord.Embed(
            title="## __Self Roles__",
            description=(
                "Hey there! Want to stay in the loop with everything happening at **Akasa Air Virtual?** "
                "Take a moment to pick your notification roles below so you only get updates that matter to you. "
                "Choose one, a few, or all — it's totally your call!\n\n"

                "- 🛫 **Group Flights** – Get pinged when someone is looking to fly together.\n"
                "- 🗺️ **Featured** – Be the first to see pilot spotlights, top screenshots, and VA highlights.\n"
                "- 📣 **Announcements** – Get notified when we post official news or updates.\n"
                "- <:IFATC:1389866636118462494> **IFATC Member** – Select this if you're part of IFATC.\n"
                "- <:IFAET:1389866639805255733> **IFAET Member** – Choose this if you're part of IFAET."
            ),
            color=discord.Color.orange()
        )

        await channel.send(embed=embed, view=SelfRoleView())

        await interaction.response.send_message("✅ Self role panel sent", ephemeral=True)


async def setup(bot):
    await bot.add_cog(SelfRoles(bot))
    
