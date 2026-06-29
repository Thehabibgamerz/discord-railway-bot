import discord
from discord.ext import commands

WELCOME_CHANNEL_ID = 1389838941414232214
RECRUIT_ROLE_ID = 1389877024406896762

BANNER_URL = "https://cdn.discordapp.com/attachments/1475055183489663158/1521009221532123216/Copy_of_QPVA_Support_20260629_095446_0000.jpg?ex=6a4345b9&is=6a41f439&hm=8033631e38f984b5782fceb458c2066dcac77b1900147a2de91a808187c13622&"
# ⚠️ Replace the above URL with your actual banner image URL.
# Upload your banner to imgur.com or Discord (right-click → Copy Link)
# and paste it above.


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):

        # ================= AUTO ASSIGN RECRUIT ROLE =================
        recruit_role = member.guild.get_role(RECRUIT_ROLE_ID)
        if recruit_role:
            try:
                await member.add_roles(recruit_role, reason="Auto-assigned on join")
            except discord.Forbidden:
                print("❌ Missing permission to assign recruit role")
            except discord.HTTPException as e:
                print(f"❌ Failed to assign recruit role: {e}")

        # ================= WELCOME CHANNEL EMBED =================
        channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title=f"Welcome to Akasa Air Virtual, {member.display_name}! ✈️",
                description=(
                    f"Hey {member.mention}, we're thrilled to have you onboard!\n\n"
                    "Akasa Air Virtual is an Infinite Flight virtual airline "
                    "dedicated to providing a realistic and enjoyable flying experience.\n\n"
                    "**🇮🇳 It's your sky — let's fly together!**"
                ),
                color=discord.Color.orange()
            )

            embed.set_image(url=BANNER_URL)
            embed.set_thumbnail(url=member.display_avatar.url)

            embed.add_field(
                name="📌 Before You Start",
                value=(
                    "• Read our rules in <#1389838715647692900>\n"
                    "• Review important info in the info channels\n"
                    "• Open a recruitment ticket to apply"
                ),
                inline=False
            )

            embed.add_field(
                name="🚀 Getting Started",
                value=(
                    "• Get your callsign assigned by staff\n"
                    "• Check the rank structure channel\n"
                    "• Join a group flight or start flying solo"
                ),
                inline=False
            )

            embed.add_field(
                name="❓ Need Help?",
                value="Open a ticket in our support channel and our staff team will assist you.",
                inline=False
            )

            embed.set_footer(
                text=f"Member #{member.guild.member_count} • Akasa Air Virtual",
                icon_url=member.guild.icon.url if member.guild.icon else None
            )

            try:
                await channel.send(
                    content=f"🎉 Everyone welcome {member.mention} to **Akasa Air Virtual**!",
                    embed=embed
                )
            except discord.Forbidden:
                print("❌ Missing permission to send in welcome channel")
            except discord.HTTPException as e:
                print(f"❌ Failed to send welcome message: {e}")

        # ================= WELCOME DM =================
        dm_embed = discord.Embed(
            title="Welcome to Akasa Air Virtual! ✈️",
            description=(
                f"Hey **{member.display_name}**,\n\n"
                "Thank you for joining **Akasa Air Virtual** — "
                "India's premier Infinite Flight virtual airline!\n\n"
                "We're excited to have you as part of our community. "
                "Here's everything you need to get started."
            ),
            color=discord.Color.orange()
        )

        dm_embed.set_image(url=BANNER_URL)
        dm_embed.set_thumbnail(url=member.guild.icon.url if member.guild.icon else None)

        dm_embed.add_field(
            name="📋 Step 1 — Read the Rules",
            value="Head to our rules channel and familiarise yourself with our guidelines.",
            inline=False
        )

        dm_embed.add_field(
            name="🎫 Step 2 — Open a Recruitment Ticket",
            value="Go to the ticket channel and open a **Recruitment** ticket to begin your application.",
            inline=False
        )

        dm_embed.add_field(
            name="🪪 Step 3 — Get Your Callsign",
            value="Once accepted, staff will assign you a unique callsign (e.g. **201QP**).",
            inline=False
        )

        dm_embed.add_field(
            name="✈️ Step 4 — Start Flying!",
            value="Check the rank structure, pick your aircraft, and take to the skies on Infinite Flight.",
            inline=False
        )

        dm_embed.add_field(
            name="🔗 Server Link",
            value="[Click here to return to the server](https://discord.gg/5NgdbnN5N8)",
            inline=False
        )

        dm_embed.set_footer(text="Akasa Air Virtual • It's your sky 🇮🇳")

        try:
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass  # Member has DMs closed — not an error worth logging loudly


async def setup(bot):
    await bot.add_cog(Welcome(bot))
