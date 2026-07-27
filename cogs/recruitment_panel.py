import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
import os

STAFF_ROLE_ID = 1389824693388837035
EXEC_ROLE_ID = 1389824452778262589

# ================= MESSAGES =================

MESSAGES = {
    "written_test": {
        "label": "Written Test",
        "emoji": "📝",
        "style": discord.ButtonStyle.primary,
        "template": """## Pilot Written Test

Dear Applicant, {mention}

Thank you for your interest in joining Akasa Air Virtual. Before proceeding, please complete the Pilot Written Test to help us assess your knowledge and readiness for operations.

👉 **Written Test:** *If you're ready type `/startwrittentest` to start the test.*

**Preparation Material — Please Read Carefully**

To ensure the best chance of success, review the following sections of the pilot manual:

1. Flying Guide
2. ATC Guide

Once you have completed the test, our recruitment team will review your submission and contact you with the next steps.

Good Luck 🤞!"""
    },
    "choose_callsign": {
        "label": "Choose Callsign",
        "emoji": "🪪",
        "style": discord.ButtonStyle.success,
        "template": """## ✅ Written Test Passed

Congratulations! 🎉 You've passed the written test.

**✈️ Next Step**

Choose a callsign number between **101–999** and reply in your recruitment ticket.

**Format Example:** QPVA123
*(First come, first served)*

Our team will confirm your callsign soon 👍"""
    },
    "join_crew_centre": {
        "label": "Join Crew Centre",
        "emoji": "🧑‍✈️",
        "style": discord.ButtonStyle.success,
        "template": """## 🧑‍✈️ Crew Centre Access

Your callsign has been successfully reserved and your account is ready.
Please join our Crew Centre using the link below to continue your onboarding and complete your profile setup.

**🔗 Crew Centre:** https://crew-center-qpva.vercel.app

Once logged in, you'll be guided through the remaining steps.

**✈️ Next Step**

You will now proceed to the **Practical Test**, where you'll demonstrate your flying skills and procedures.

👉 Let me know when you're ready, and I'll provide more details about the practical test.

Good luck — you're almost ready to join **Akasa Air Virtual ✈️**"""
    },
    "practical_test": {
        "label": "Practical Test",
        "emoji": "🛫",
        "style": discord.ButtonStyle.primary,
        "template": """## 🛫 Practical Test Details

Hey {mention},
Here are the instructions for your **Practical Test** with **Akasa Air Virtual**. Please read carefully before starting.

**✈️ Flight Information**
**- Aircraft:** Boeing 737-8 MAX (B38M)
**- Server:** Expert Server
**- Route:** VABB - VAAH
**- Flight Type:** Full gate-to-gate flight

**✅ Requirements**
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

***Good luck — fly safe and show your best airmanship ✈️***"""
    },
    "pass": {
        "label": "Pass ✅",
        "emoji": "🎉",
        "style": discord.ButtonStyle.success,
        "template": """## 🎉 Practical Test Result — PASS

Hey {mention},

Congratulations! You have **successfully passed your Practical Flight Test** with **Akasa Air Virtual.**
Your flight demonstrated solid airmanship, good procedure adherence, and safe operations throughout the assessment.

You are now **officially approved for active duty** and will be added to the pilot roster.

- **Pick a Roles** <#1389839252883505246>

Welcome to the team — fly safe and represent us proudly ✈️"""
    },
    "fail": {
        "label": "Fail ❌",
        "emoji": "📋",
        "style": discord.ButtonStyle.danger,
        "template": """## 📋 Practical Test Result — Not Passed

Hey {mention},

Thank you for completing your Practical Flight Test with **Akasa Air Virtual.**

After review, your performance did not meet the required standards at this time.
Don't worry — you're welcome to **re-attempt** the test after additional practice.

**Examiner Feedback**
*(write here the test feedback)*

**Next Steps:**
- Review feedback from the examiner
- Contact recruitment when ready for a retest

Let us know when you feel ready, and we'll be happy to schedule your next attempt.
Keep practicing — we're here to support you"""
    }
}


def is_authorized(member: discord.Member) -> bool:
    return any(role.id in (STAFF_ROLE_ID, EXEC_ROLE_ID) for role in member.roles)


# ================= SEND MODAL =================

class SendMessageModal(Modal):
    def __init__(self, key: str, template: str):
        super().__init__(title=f"Send — {MESSAGES[key]['label']}")
        self.key = key

        self.mention = TextInput(
            label="Tag the recruit (@username)",
            placeholder="e.g. @foxtrot_lima1 or leave blank if not needed",
            required=False,
            max_length=100
        )
        self.channel_id = TextInput(
            label="Channel ID to send in",
            placeholder="Right-click the ticket channel → Copy ID",
            max_length=20
        )
        self.custom_message = TextInput(
            label="Edit message (optional — keeps template if blank)",
            style=discord.TextStyle.paragraph,
            required=False,
            default=template,
            max_length=2000
        )

        self.add_item(self.mention)
        self.add_item(self.channel_id)
        self.add_item(self.custom_message)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel_id.value.strip())
        except ValueError:
            return await interaction.response.send_message(
                "❌ Invalid channel ID.", ephemeral=True
            )

        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            return await interaction.response.send_message(
                "❌ Channel not found. Check the ID.", ephemeral=True
            )

        mention = self.mention.value.strip() if self.mention.value.strip() else ""
        message_text = self.custom_message.value if self.custom_message.value.strip() else MESSAGES[self.key]["template"]

        # Replace {mention} placeholder with actual mention
        message_text = message_text.replace("{mention}", mention)

        try:
            await channel.send(message_text)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to send in that channel.", ephemeral=True
            )

        await interaction.response.send_message(
            f"✅ **{MESSAGES[self.key]['label']}** message sent in {channel.mention}",
            ephemeral=True
        )


# ================= PANEL VIEW =================

class RecruitmentPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)

        for key, data in MESSAGES.items():
            btn = Button(
                label=data["label"],
                emoji=data["emoji"],
                style=data["style"],
                custom_id=f"recruit_{key}"
            )
            btn.callback = self._make_callback(key, data["template"])
            self.add_item(btn)

    def _make_callback(self, key: str, template: str):
        async def callback(interaction: discord.Interaction):
            if not is_authorized(interaction.user):
                return await interaction.response.send_message(
                    "❌ Only Staff and Executive Team can use this panel.", ephemeral=True
                )
            await interaction.response.send_modal(SendMessageModal(key, template))
        return callback


# ================= COG =================

class RecruitmentPanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="recruitment_panel", description="Send the Recruitment message panel (staff/exec only)")
    @app_commands.describe(
        channel="Channel to post the panel in",
        banner="Optional banner image URL for the panel embed"
    )
    async def recruitment_panel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        banner: str = None
    ):
        if not is_authorized(interaction.user):
            return await interaction.response.send_message(
                "❌ Only Staff and Executive Team can send the recruitment panel.", ephemeral=True
            )

        embed = discord.Embed(
            title="🧑‍✈️ Akasa Air Virtual — Recruitment Panel",
            description=(
                "Use the buttons below to send recruitment messages to applicants.\n\n"
                "📝 **Written Test** — Send the written test instructions\n"
                "🪪 **Choose Callsign** — Written test passed, choose a callsign\n"
                "🧑‍✈️ **Join Crew Centre** — Callsign confirmed, join the Crew Centre\n"
                "🛫 **Practical Test** — Send the practical test details\n"
                "🎉 **Pass** — Practical test passed — welcome to the team!\n"
                "📋 **Fail** — Practical test not passed\n\n"
                "Each button opens a form where you can:\n"
                "• Tag the recruit\n"
                "• Select the ticket channel\n"
                "• Edit the message before sending"
            ),
            color=discord.Color.orange()
        )

        if banner:
            embed.set_image(url=banner)

        embed.set_footer(text="AkasaAirVirtual • Recruitment Panel — Staff & Exec Only")

        view = RecruitmentPanelView()
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(
            f"✅ Recruitment panel sent in {channel.mention}", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(RecruitmentPanel(bot))
    bot.add_view(RecruitmentPanelView())
