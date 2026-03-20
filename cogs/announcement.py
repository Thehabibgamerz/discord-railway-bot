import discord
from discord.ext import commands
from discord import app_commands


# ================= EDIT MODAL =================

class EditAnnouncementModal(discord.ui.Modal, title="Edit Announcement"):

    text = discord.ui.TextInput(label="Announcement Text", style=discord.TextStyle.long)

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):

        self.view.text = self.text.value

        embed = discord.Embed(
            title="📢 Announcement Preview",
            description=self.view.text,
            color=discord.Color.orange()
        )

        embed.set_footer(
            text=f"Preview by {interaction.user}",
            icon_url=interaction.user.display_avatar.url
        )

        if self.view.image:
            embed.set_image(url=self.view.image)

        await interaction.response.defer()

        await self.view.message.edit(embed=embed, view=self.view)


# ================= VIEW =================

class AnnouncementView(discord.ui.View):

    def __init__(self, author, text, channel, role, image):
        super().__init__(timeout=600)
        self.author = author
        self.text = text
        self.channel = channel
        self.role = role
        self.image = image
        self.message = None

    # ✏️ EDIT
    @discord.ui.button(label="✏️ Edit", style=discord.ButtonStyle.secondary)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user != self.author:
            return await interaction.response.send_message("❌ Not your panel", ephemeral=True)

        await interaction.response.send_modal(EditAnnouncementModal(self))

    # 📤 SEND
    @discord.ui.button(label="📤 Send", style=discord.ButtonStyle.success)
    async def send(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user != self.author:
            return await interaction.response.send_message("❌ Not your panel", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="📢 Announcement",
            description=self.text,
            color=discord.Color.orange()
        )

        embed.set_footer(
            text=f"Announced by {interaction.user}",
            icon_url=interaction.user.display_avatar.url
        )

        if self.image:
            embed.set_image(url=self.image)

        content = self.role.mention if self.role else None

        try:
            await self.channel.send(content=content, embed=embed)
            await interaction.followup.send("✅ Announcement sent!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed: {e}", ephemeral=True)


# ================= COMMAND =================

class Announcement(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="announcement", description="Create an announcement with preview")
    @app_commands.describe(
        text="Announcement message",
        channel="Channel to send",
        role="Optional role ping",
        image="Optional image URL"
    )
    async def announcement(
        self,
        interaction: discord.Interaction,
        text: str,
        channel: discord.TextChannel,
        role: discord.Role = None,
        image: str = None
    ):

        if not interaction.user.guild_permissions.manage_messages:
            return await interaction.response.send_message(
                "❌ You don't have permission.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="📢 Announcement Preview",
            description=text,
            color=discord.Color.orange()
        )

        embed.set_footer(
            text=f"Preview by {interaction.user}",
            icon_url=interaction.user.display_avatar.url
        )

        if image:
            embed.set_image(url=image)

        view = AnnouncementView(interaction.user, text, channel, role, image)

        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True
        )

        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(Announcement(bot))
