import discord
from discord.ext import commands
from discord import app_commands


WELCOME_CHANNEL_ID = 1389838941414232214  # 🔁 replace
WELCOME_ROLE_ID = None  # optional (set role ID or keep None)


class Welcome(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):

        channel = member.guild.get_channel(WELCOME_CHANNEL_ID)

        if not channel:
            return

        # Create embed
        embed = discord.Embed(
            title="✈️ Welcome Aboard!",
            description=(
                f"Welcome {member.mention} to **Akasa Air Virtual**!\n\n"
                "We're excited to have you join our airline.\n"
                "Please read the rules and start your journey with us!\n\n"
                "🧑‍✈️ Join flights\n"
                "📋 Submit PIREPs\n"
                "🗺️ Explore routes\n\n"
                f"You are member **#{member.guild.member_count}** 🎉"
            ),
            color=discord.Color.orange()
        )

        # User avatar
        embed.set_thumbnail(url=member.display_avatar.url)

        # Custom background image
        embed.set_image(url="https://cdn.discordapp.com/attachments/1475411366901714978/1475418227957043252/WELCOME_20260223_143453_0000.png?ex=69be5f4d&is=69bd0dcd&hm=6e48de2868cf97a530c41f93627ae6e627991c80d66f8b284f2a52a52cf617a2")  # 🔁 replace

        # Footer
        embed.set_footer(text=f"{member.name} joined", icon_url=member.display_avatar.url)

        # Optional role ping
        content = None
        if WELCOME_ROLE_ID:
            content = f"<@&{WELCOME_ROLE_ID}>"

        await channel.send(content=content, embed=embed)


async def setup(bot):
    await bot.add_cog(Welcome(bot))
