import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO

WELCOME_CHANNEL_ID = 1389838941414232214  # 🔁 replace
WELCOME_ROLE_ID = None  # optional


class Welcome(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def create_banner(self, member: discord.Member):
        # Load background
        bg = Image.open("welcome_bg.png").convert("RGBA")  # 🔁 add your background file

        # Get user avatar
        avatar_url = member.display_avatar.url
        response = requests.get(avatar_url)
        avatar = Image.open(BytesIO(response.content)).convert("RGBA")

        # Resize avatar
        avatar = avatar.resize((200, 200))

        # Make avatar circle
        mask = Image.new("L", avatar.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, 200, 200), fill=255)
        avatar.putalpha(mask)

        # Paste avatar on background
        bg.paste(avatar, (50, 100), avatar)

        # Draw text
        draw = ImageDraw.Draw(bg)

        try:
            font_big = ImageFont.truetype("arial.ttf", 60)
            font_small = ImageFont.truetype("arial.ttf", 40)
        except:
            font_big = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # Text
        draw.text((300, 120), "WELCOME", font=font_big, fill="white")
        draw.text((300, 200), member.name, font=font_small, fill="orange")

        # Save to bytes
        buffer = BytesIO()
        bg.save(buffer, format="PNG")
        buffer.seek(0)

        return buffer

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):

        channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if not channel:
            return

        # 🎨 Create banner
        banner = await self.create_banner(member)

        file = discord.File(fp=banner, filename="welcome.png")

        # ✨ Clean text message
        content = (
            f"🇮🇳✈️ **Welcome to Akasa Air Virtual, {member.mention}!**\n\n"

            "We’re delighted to have you onboard our airline community.\n\n"

            "**📌 Before you start:**\n"
            "• Read our rules: #📒・rules\n"
            "• Review important info: #📌・important-info\n"
            "• Open a recruitment ticket: #📬・open a ticket\n\n"

            "**🚀 Getting Started:**\n"
            "Our staff team will guide you through your onboarding process.\n\n"

            "If you have any questions, feel free to ask — we’re here to help.\n\n"

            "✈️ Enjoy your journey in Infinite Flight skies!\n\n"

            f"🎉 Member **#{member.guild.member_count}**"
        )

        # Role ping
        if WELCOME_ROLE_ID:
            content = f"<@&{WELCOME_ROLE_ID}>\n\n" + content

        await channel.send(content=content, file=file)


async def setup(bot):
    await bot.add_cog(Welcome(bot))
