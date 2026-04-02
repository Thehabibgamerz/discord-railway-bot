import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button

# ✅ YOUR UPDATED ROLE IDs
GROUP_ROLE = 1432617344068227102
FEATURED_ROLE = 1432617094956060683
ANNOUNCE_ROLE = 1432617170801791049
IFATC_ROLE = 1389833550957641840
IFAET_ROLE = 1389833738128719883

# 🔁 ADD YOUR LOGO HERE
LOGO_URL = "https://your-logo-url.png"


# ================= VIEW =================

class RoleView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def toggle(self, interaction, role_id):
        role = interaction.guild.get_role(role_id)

        if not role:
            return await interaction.response.send_message("❌ Role not found", ephemeral=True)

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"❌ Removed **{role.name}**", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Added **{role.name}**", ephemeral=True)

    # Row 1
    @discord.ui.button(label="Group Flights", emoji="🛫", style=discord.ButtonStyle.secondary, row=0, custom_id="rr_group")
    async def group(self, interaction: discord.Interaction, button: Button):
        await self.toggle(interaction, GROUP_ROLE)

    @discord.ui.button(label="Featured", emoji="🗺️", style=discord.ButtonStyle.secondary, row=0, custom_id="rr_featured")
    async def featured(self, interaction: discord.Interaction, button: Button):
        await self.toggle(interaction, FEATURED_ROLE)

    @discord.ui.button(label="Announcements", emoji="📣", style=discord.ButtonStyle.secondary, row=0, custom_id="rr_announce")
    async def announce(self, interaction: discord.Interaction, button: Button):
        await self.toggle(interaction, ANNOUNCE_ROLE)

    # Row 2
    @discord.ui.button(label="IFATC Member", emoji="<:IFATC:1389866636118462494>", style=discord.ButtonStyle.primary, row=1, custom_id="rr_ifatc")
    async def ifatc(self, interaction: discord.Interaction, button: Button):
        await self.toggle(interaction, IFATC_ROLE)

    @discord.ui.button(label="IFAET Member", emoji="<:IFAET:1389866639805255733>", style=discord.ButtonStyle.primary, row=1, custom_id="rr_ifaet")
    async def ifaet(self, interaction: discord.Interaction, button: Button):
        await self.toggle(interaction, IFAET_ROLE)


# ================= COG =================

class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="reactionrole", description="Send self roles panel")
    async def reactionrole(self, interaction: discord.Interaction, channel: discord.TextChannel):

        # ✅ EXACT EMBED (UNCHANGED)
        embed = discord.Embed(
            description=(
                "## __Self Roles__\n\n"
                "Hey there! Want to stay in the loop with everything happening at **Akasa Air Virtual?** "
                "Take a moment to pick your notification roles below so you only get updates that matter to you. "
                "Choose one, a few, or all — it's totally your call!\n\n"

                "- 🛫 **Group Flights** – Get pinged when someone is looking to fly together.\n"
                "- 🗺️ **Featured** – Be the first to see pilot spotlights, top screenshots, and VA highlights.\n"
                "- 📣 **Announcements** – Get notified when we post official news or updates.\n"
                "- <:IFATC:1389866636118462494> **IFATC Member** – Select this if you're part of IFATC so you can access our dedicated channels and coordination tools.\n"
                "- <:IFAET:1389866639805255733> **IFAET Member** – Choose this if you're part of IFAET to be recognized and collaborate with fellow editors."
            ),
            color=discord.Color.orange()
        )

        # ✅ LOGO (top right)
        embed.set_thumbnail(url=LOGO_URL)

        view = RoleView()

        await channel.send(embed=embed, view=view)

        await interaction.response.send_message(
            f"✅ Panel sent to {channel.mention}",
            ephemeral=True
        )


# ================= SETUP =================

async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))
