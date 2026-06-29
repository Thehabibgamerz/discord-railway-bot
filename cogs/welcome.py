import discord
from discord.ext import commands

WELCOME_CHANNEL_ID = 1389838941414232214
RECRUIT_ROLE_ID = 1389877024406896762

BANNER_URL = "https://cdn.discordapp.com/attachments/1475055183489663158/1521102855858028655/Copy_of_QPVA_Support_20260629_160931_0000.jpg?ex=6a439ced&is=6a424b6d&hm=2e26059b3a862e2065fd97bc86d7c3ef74f9700f4f5cabd902625ce606f6bc7a&"
# ⚠️ Replace with your actual banner image URL (upload to imgur or Discord)


GOODBYE_CHANNEL_ID = 1389842080767148052


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        channel = member.guild.get_channel(GOODBYE_CHANNEL_ID)
        if not channel:
            return
        try:
            await channel.send(
                f"✈️ **{member.mention}** ({member.name}) has left the server. "
                f"We wish them safe skies ahead. 🇮🇳"
            )
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

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

            # Banner image — no thumbnail on server embed
            embed.set_image(url=BANNER_URL)

            embed.add_field(
                name="📌 Before You Start",
                value=(
                    f"• Read our rules: <#1389836240278519890>\n"
                    f"• Review important info: <#1389839170167373975>\n"
                    f"• Open a recruitment ticket: <#1479253647643775006>"
                ),
                inline=False
            )

            embed.add_field(
                name="🚀 Getting Started",
                value="Our staff team will guide you through the onboarding process.",
                inline=False
            )

            embed.add_field(
                name="❓ Need Help?",
                value="Open a ticket and our staff team will assist you.",
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

        # Banner + server icon thumbnail on DM
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
            pass  # Member has DMs closed


async def setup(bot):
    await bot.add_cog(Welcome(bot))
