import discord
from discord.ext import commands
from discord import app_commands


# ================= MODAL =================

class EmbedModal(discord.ui.Modal, title="Edit Embed"):

    title_input = discord.ui.TextInput(label="Title", required=False)
    description_input = discord.ui.TextInput(label="Description", style=discord.TextStyle.long)

    image_input = discord.ui.TextInput(label="Image URL", required=False)
    thumbnail_input = discord.ui.TextInput(label="Thumbnail URL", required=False)
    footer_input = discord.ui.TextInput(label="Footer", required=False)

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title=self.title_input.value or None,
            description=self.description_input.value,
            color=discord.Color.orange()
        )

        if self.image_input.value:
            embed.set_image(url=self.image_input.value)

        if self.thumbnail_input.value:
            embed.set_thumbnail(url=self.thumbnail_input.value)

        if self.footer_input.value:
            embed.set_footer(text=self.footer_input.value)

        for field in self.view.fields:
            embed.add_field(name=field["name"], value=field["value"], inline=False)

        self.view.embed = embed

        await interaction.response.defer()

        try:
            if self.view.message:
                await self.view.message.edit(
                    content="🧪 Preview",
                    embed=embed,
                    view=self.view
                )
            else:
                await interaction.followup.send("⚠️ Preview not found.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)


# ================= FIELD MODAL =================

class FieldModal(discord.ui.Modal, title="Add Field"):

    name = discord.ui.TextInput(label="Field Name")
    value = discord.ui.TextInput(label="Field Value", style=discord.TextStyle.long)

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        self.view.fields.append({
            "name": self.name.value,
            "value": self.value.value
        })
        await interaction.response.send_message("✅ Field added!", ephemeral=True)


# ================= BUTTON MODAL =================

class ButtonModal(discord.ui.Modal, title="Add Button"):

    label = discord.ui.TextInput(label="Button Label")
    url = discord.ui.TextInput(label="Button URL")

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        self.view.buttons.append({
            "label": self.label.value,
            "url": self.url.value
        })
        await interaction.response.send_message("✅ Button added!", ephemeral=True)


# ================= MAIN VIEW =================

class EmbedView(discord.ui.View):

    def __init__(self, author):
        super().__init__(timeout=600)
        self.author = author
        self.embed = None
        self.channel = None
        self.fields = []
        self.buttons = []
        self.role_ping = None
        self.message = None

    def build_buttons(self):
        view = discord.ui.View()
        for b in self.buttons:
            view.add_item(discord.ui.Button(label=b["label"], url=b["url"]))
        return view

    # EDIT
    @discord.ui.button(label="✏️ Edit", style=discord.ButtonStyle.primary)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.author and interaction.user != self.author:
            return await interaction.response.send_message("❌ Not your panel", ephemeral=True)
        await interaction.response.send_modal(EmbedModal(self))

    # ADD FIELD
    @discord.ui.button(label="➕ Field", style=discord.ButtonStyle.secondary)
    async def add_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.author and interaction.user != self.author:
            return await interaction.response.send_message("❌ Not your panel", ephemeral=True)
        await interaction.response.send_modal(FieldModal(self))

    # ADD BUTTON
    @discord.ui.button(label="🔘 Button", style=discord.ButtonStyle.secondary)
    async def add_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.author and interaction.user != self.author:
            return await interaction.response.send_message("❌ Not your panel", ephemeral=True)
        await interaction.response.send_modal(ButtonModal(self))

    # ROLE SELECT
    @discord.ui.select(
        placeholder="📢 Select role to ping (optional)",
        cls=discord.ui.RoleSelect,
        min_values=0,
        max_values=1
    )
    async def select_role(self, interaction: discord.Interaction, select):
        if self.author and interaction.user != self.author:
            return await interaction.response.send_message("❌ Not your panel", ephemeral=True)

        if select.values:
            self.role_ping = select.values[0]
            await interaction.response.send_message(
                f"✅ Selected role: {self.role_ping.mention}",
                ephemeral=True
            )
        else:
            self.role_ping = None
            await interaction.response.send_message("❌ Role cleared.", ephemeral=True)

    # CHANNEL SELECT (FIXED)
    @discord.ui.select(
        placeholder="Select channel...",
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text]
    )
    async def select_channel(self, interaction: discord.Interaction, select):
        if self.author and interaction.user != self.author:
            return await interaction.response.send_message("❌ Not your panel", ephemeral=True)

        channel_obj = select.values[0]
        self.channel = interaction.guild.get_channel(channel_obj.id)

        await interaction.response.send_message(
            f"📍 Channel set: {self.channel.mention}",
            ephemeral=True
        )

    # SEND BUTTON (FIXED)
    @discord.ui.button(label="📤 Send", style=discord.ButtonStyle.success)
    async def send(self, interaction: discord.Interaction, button: discord.ui.Button):

        if self.author and interaction.user != self.author:
            return await interaction.response.send_message("❌ Not your panel", ephemeral=True)

        if not self.embed or not self.channel:
            return await interaction.response.send_message(
                "⚠️ Create embed & select channel first.",
                ephemeral=True
            )

        if not isinstance(self.channel, discord.TextChannel):
            return await interaction.response.send_message(
                "❌ Invalid channel selected.",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        try:
            content = self.role_ping.mention if self.role_ping else None

            await self.channel.send(
                content=content,
                embed=self.embed,
                view=self.build_buttons() if self.buttons else None
            )

            await interaction.followup.send("✅ Embed sent successfully!", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ Failed: {e}", ephemeral=True)


# ================= COMMAND =================

class EmbedBuilder(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="embedui", description="Advanced embed builder")
    async def embedui(self, interaction: discord.Interaction):

        view = EmbedView(interaction.user)

        await interaction.response.send_message(
            "🛠️ **Advanced Embed Builder**\n\n"
            "✏️ Edit embed\n"
            "➕ Add fields\n"
            "🔘 Add buttons\n"
            "📢 Select role\n"
            "📤 Send when ready",
            view=view,
            ephemeral=True
        )

        view.message = await interaction.original_response()


async def setup(bot):
    await bot.add_cog(EmbedBuilder(bot))
