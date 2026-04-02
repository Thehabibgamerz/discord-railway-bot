import discord
from discord.ext import commands

WELCOME_CHANNEL_ID = 1389838941414232214  # 🔁 your channel ID
WELCOME_ROLE_ID = None  # optional role ping


class Welcome(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):

        # Get channel
        channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if not channel:
            print("❌ Welcome channel not found")
            return

        # Clean welcome message
        message = (
            f"🇮🇳✈️ **Welcome to Akasa Air Virtual, {member.mention}!**\n\n"

            "We’re delighted to have you onboard our airline community.\n\n"

            "**📌 Before you start:**\n"
            "• Read our rules: #📒・rules\n"
            "• Review important info: #📌・important-info\n"
            "• Open a recruitment ticket: #📬・open a ticket\n\n"

            "**🚀 Getting Started:**\n"
            "Our staff team will guide you through the onboarding process.\n\n"

            "If you have any questions, feel free to ask — we’re here to help.\n\n"

            "✈️ Enjoy your journey in Infinite Flight skies!\n\n"

            f"🎉 You are member **#{member.guild.member_count}**"
        )

        # Optional role ping
        if WELCOME_ROLE_ID:
            message = f"<@&{WELCOME_ROLE_ID}>\n\n" + message

        # Send message
        try:
            await channel.send(message)
        except Exception as e:
            print(f"❌ Failed to send welcome message: {e}")


async def setup(bot):
    await bot.add_cog(Welcome(bot))
