import discord
from discord.ext import commands
from discord import app_commands

STAFF_ROLE = 1389824693388837035


class Nickname(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="nickname", description="Change a user's nickname")
    async def nickname(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        nickname: str | None = None
    ):

        # Check staff permission
        if STAFF_ROLE not in [role.id for role in interaction.user.roles]:
            await interaction.response.send_message(
                "❌ Only staff can use this command.",
                ephemeral=True
            )
            return

        try:
            await member.edit(nick=nickname)

            if nickname:
                description = f"✏️ {member.mention}'s nickname has been changed to **{nickname}**."
            else:
                description = f"♻️ {member.mention}'s nickname has been **reset**."

            embed = discord.Embed(
                title="Nickname Updated",
                description=description,
                color=discord.Color.orange()
            )

            await interaction.response.send_message(embed=embed)

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to change this user's nickname.",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(Nickname(bot))
