import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Modal, TextInput

STAFF_ROLE_ID = 1389824693388837035
EXEC_ROLE_ID = 1389824452778262589


def is_authorized(member: discord.Member) -> bool:
    return any(role.id in (STAFF_ROLE_ID, EXEC_ROLE_ID) for role in member.roles)


ONBOARDING_TEMPLATE = """## Welcome to Akasa Air Virtual!

Dear Pilot, {ifc_username}

We're delighted to have you join our community and begin your journey with us. You're now part of a team passionate about aviation, realism, and great experiences in the virtual skies.

**__Next Steps__**
1. Join our [Discord Server](https://discord.gg/UvGM2aN4mh)
2. Go to # 📬・support-ticket and open a "Recruitment" ticket

We're excited to have you onboard and look forward to flying with you soon. Welcome aboard! ✈️

Best regards,
QPVA Recruitment Team!"""


class OnboardModal(Modal):
    def __init__(self, member: discord.Member):
        super().__init__(title=f"Onboard — {member.display_name}")
        self.member = member

        self.ifc_username = TextInput(
            label="IFC Username",
            placeholder="e.g. TheHabib_Gamerz",
            max_length=50
        )
        self.add_item(self.ifc_username)

    async def on_submit(self, interaction: discord.Interaction):
        ifc = self.ifc_username.value.strip()
        message = ONBOARDING_TEMPLATE.replace("{ifc_username}", ifc)

        try:
            await self.member.send(message)
        except discord.Forbidden:
            return await interaction.response.send_message(
                f"❌ Could not DM **{self.member.display_name}** — their DMs may be closed.",
                ephemeral=True
            )
        except Exception as e:
            return await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

        await interaction.response.send_message(
            f"✅ Onboarding message sent to **{self.member.display_name}** (`{ifc}`).",
            ephemeral=True
        )


class Onboarding(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="onboard", description="Send onboarding DM to a member (staff only)")
    @app_commands.describe(member="The member to onboard")
    async def onboard(self, interaction: discord.Interaction, member: discord.Member):
        if not is_authorized(interaction.user):
            return await interaction.response.send_message(
                "❌ Only Staff and Executive Team can use this command.", ephemeral=True
            )

        if member.bot:
            return await interaction.response.send_message(
                "❌ You cannot onboard a bot.", ephemeral=True
            )

        await interaction.response.send_modal(OnboardModal(member))


async def setup(bot):
    await bot.add_cog(Onboarding(bot))
