import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput

STAFF_ROLE_ID = 1389824693388837035
EXEC_ROLE_ID = 1389824452778262589

WRITTEN_TEST_MSG = """## Pilot Written Test

Dear Applicant, {mention}

Thank you for your interest in joining Akasa Air Virtual. Before proceeding, please complete the Pilot Written Test to help us assess your knowledge and readiness for operations.

\U0001f449 **Written Test:** *If you're ready type `/startwrittentest` to start the test.*

**Preparation Material \u2014 Please Read Carefully**

To ensure the best chance of success, review the following sections of the pilot manual:

1. Flying Guide
2. ATC Guide

Once you have completed the test, our recruitment team will review your submission and contact you with the next steps.

Good Luck \U0001f91e!"""

CALLSIGN_MSG = """## \u2705 Written Test Passed

Congratulations! \U0001f389 You've passed the written test.

**\u2708\ufe0f Next Step**

Choose a callsign number between **101\u2013999** and reply in your recruitment ticket.

**Format Example:** QPVA123
*(First come, first served)*

Our team will confirm your callsign soon \U0001f44d"""

CREW_CENTRE_MSG = """## \U0001f9d1\u200d\u2708\ufe0f Crew Centre Access

Your callsign has been successfully reserved and your account is ready.
Please join our Crew Centre using the link below to continue your onboarding and complete your profile setup.

**\U0001f517 Crew Centre:** https://crew-center-qpva.vercel.app

Once logged in, you'll be guided through the remaining steps.

**\u2708\ufe0f Next Step**

You will now proceed to the **Practical Test**, where you'll demonstrate your flying skills and procedures.

\U0001f449 Let me know when you're ready, and I'll provide more details about the practical test.

Good luck \u2014 you're almost ready to join **Akasa Air Virtual \u2708\ufe0f**"""

PRACTICAL_TEST_MSG = """## \U0001f6eb Practical Test Details

Hey {mention},
Here are the instructions for your **Practical Test** with **Akasa Air Virtual**. Please read carefully before starting.

**\u2708\ufe0f Flight Information**
**- Aircraft:** Boeing 737-8 MAX (B38M)
**- Server:** Expert Server
**- Route:** VABB - VAAH
**- Flight Type:** Full gate-to-gate flight

**\u2705 Requirements**
- Use your assigned callsign (e.g., Akasa Air 123CR)
- Generate & follow a **SimBrief flight plan**
- Complete a full **gate-to-gate flight**
- Follow ATC instructions (if available)
- Maintain proper taxi speed and procedures
- Conduct approach briefing
- Ensure a **stable approach** and smooth landing
- Taxi to stand and end flight properly

After completing the test, send the replay file here.
Our team will review your performance and provide your result.

***Good luck \u2014 fly safe and show your best airmanship \u2708\ufe0f***"""

PASS_MSG = """## \U0001f389 Practical Test Result \u2014 PASS

Hey {mention},

Congratulations! You have **successfully passed your Practical Flight Test** with **Akasa Air Virtual.**
Your flight demonstrated solid airmanship, good procedure adherence, and safe operations throughout the assessment.

You are now **officially approved for active duty** and will be added to the pilot roster.

- **Pick a Roles** <#1389839252883505246>

Welcome to the team \u2014 fly safe and represent us proudly \u2708\ufe0f"""

FAIL_MSG = """## \U0001f4cb Practical Test Result \u2014 Not Passed

Hey {mention},

Thank you for completing your Practical Flight Test with **Akasa Air Virtual.**

After review, your performance did not meet the required standards at this time.
Don't worry \u2014 you're welcome to **re-attempt** the test after additional practice.

**Examiner Feedback**
*(write here the test feedback)*

**Next Steps:**
- Review feedback from the examiner
- Contact recruitment when ready for a retest

Let us know when you feel ready, and we'll be happy to schedule your next attempt.
Keep practicing \u2014 we're here to support you"""


def is_authorized(member: discord.Member) -> bool:
    return any(role.id in (STAFF_ROLE_ID, EXEC_ROLE_ID) for role in member.roles)


# ================= SEND MODAL =================

class SendModal(Modal):
    def __init__(self, label: str, template: str):
        super().__init__(title=f"Send — {label}")
        self.template = template

        self.mention = TextInput(
            label="Tag the recruit (or leave blank)",
            placeholder="e.g. @foxtrot_lima1",
            required=False,
            max_length=100
        )
        self.channel_id = TextInput(
            label="Ticket Channel ID",
            placeholder="Right-click channel → Copy ID",
            max_length=20
        )
        self.extra_note = TextInput(
            label="Extra note to append (optional)",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500,
            placeholder="Leave blank to send the default template as-is"
        )

        self.add_item(self.mention)
        self.add_item(self.channel_id)
        self.add_item(self.extra_note)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            ch_id = int(self.channel_id.value.strip())
        except ValueError:
            return await interaction.response.send_message("❌ Invalid channel ID.", ephemeral=True)

        channel = interaction.guild.get_channel(ch_id)
        if not channel:
            return await interaction.response.send_message("❌ Channel not found.", ephemeral=True)

        mention = self.mention.value.strip()
        text = self.template.replace("{mention}", mention)

        if self.extra_note.value.strip():
            text += f"\n\n{self.extra_note.value.strip()}"

        try:
            await channel.send(text)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ No permission to send in that channel.", ephemeral=True
            )
        except Exception as e:
            return await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

        await interaction.response.send_message(
            f"✅ Message sent in {channel.mention}", ephemeral=True
        )


# ================= PANEL VIEW =================

class RecruitmentPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _auth(self, interaction: discord.Interaction) -> bool:
        if not is_authorized(interaction.user):
            await interaction.response.send_message(
                "❌ Only Staff and Executive Team can use this panel.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Written Test", emoji="📝", style=discord.ButtonStyle.primary, custom_id="rp_written_test", row=0)
    async def written_test(self, interaction: discord.Interaction, button: Button):
        if not await self._auth(interaction):
            return
        await interaction.response.send_modal(SendModal("Written Test", WRITTEN_TEST_MSG))

    @discord.ui.button(label="Choose Callsign", emoji="🪪", style=discord.ButtonStyle.success, custom_id="rp_callsign", row=0)
    async def choose_callsign(self, interaction: discord.Interaction, button: Button):
        if not await self._auth(interaction):
            return
        await interaction.response.send_modal(SendModal("Choose Callsign", CALLSIGN_MSG))

    @discord.ui.button(label="Join Crew Centre", emoji="🧑‍✈️", style=discord.ButtonStyle.success, custom_id="rp_crew_centre", row=1)
    async def join_crew_centre(self, interaction: discord.Interaction, button: Button):
        if not await self._auth(interaction):
            return
        await interaction.response.send_modal(SendModal("Join Crew Centre", CREW_CENTRE_MSG))

    @discord.ui.button(label="Practical Test", emoji="🛫", style=discord.ButtonStyle.primary, custom_id="rp_practical_test", row=1)
    async def practical_test(self, interaction: discord.Interaction, button: Button):
        if not await self._auth(interaction):
            return
        await interaction.response.send_modal(SendModal("Practical Test", PRACTICAL_TEST_MSG))

    @discord.ui.button(label="Pass ✅", emoji="🎉", style=discord.ButtonStyle.success, custom_id="rp_pass", row=2)
    async def result_pass(self, interaction: discord.Interaction, button: Button):
        if not await self._auth(interaction):
            return
        await interaction.response.send_modal(SendModal("Pass", PASS_MSG))

    @discord.ui.button(label="Fail ❌", emoji="📋", style=discord.ButtonStyle.danger, custom_id="rp_fail", row=2)
    async def result_fail(self, interaction: discord.Interaction, button: Button):
        if not await self._auth(interaction):
            return
        await interaction.response.send_modal(SendModal("Fail", FAIL_MSG))


# ================= COG =================

class RecruitmentPanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="recruitment_panel", description="Send the Recruitment panel (staff/exec only)")
    @app_commands.describe(
        channel="Channel to post the panel in",
        banner="Optional banner image URL"
    )
    async def recruitment_panel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        banner: str = None
    ):
        if not is_authorized(interaction.user):
            return await interaction.response.send_message(
                "❌ Only Staff and Executive Team can send this panel.", ephemeral=True
            )

        embed = discord.Embed(
            title="🧑‍✈️ Akasa Air Virtual — Recruitment Panel",
            description=(
                "Use the buttons below to send recruitment messages to applicants.\n\n"
                "📝 **Written Test** — Send written test instructions\n"
                "🪪 **Choose Callsign** — Test passed, choose a callsign\n"
                "🧑‍✈️ **Join Crew Centre** — Callsign confirmed, join Crew Centre\n"
                "🛫 **Practical Test** — Send practical test details\n"
                "🎉 **Pass** — Practical test passed\n"
                "📋 **Fail** — Practical test not passed\n\n"
                "Each button lets you tag the recruit, pick the channel, and edit the message before sending."
            ),
            color=discord.Color.orange()
        )

        if banner:
            embed.set_image(url=banner)

        embed.set_footer(text="AkasaAirVirtual • Recruitment Panel")

        await channel.send(embed=embed, view=RecruitmentPanelView())
        await interaction.response.send_message(
            f"✅ Recruitment panel sent in {channel.mention}", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(RecruitmentPanel(bot))
    bot.add_view(RecruitmentPanelView())
