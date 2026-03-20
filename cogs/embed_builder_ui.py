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
            title=self.title_input.value if self.title_input.value else None,
            description=self.description_input.value,
            color=discord.Color.orange()
        )

        if self.image_input.value:
            embed.set_image(url=self.image_input.value)

        if self.thumbnail_input.value:
            embed.set_thumbnail(url=self.thumbnail_input.value)

        if self.footer_input.value:
            embed.set_footer(text=self.footer_input.value)

        # Add fields if exist
        for field in self.view.fields:
            embed.add_field(name=field["name"], value=field["value"], inline=False)

        self.view.embed = embed

        await interaction.response.edit_message(
            content="✅ Preview updated",
            embed=embed,
            view=self.view
        )


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


# ================= VIEW =================

class EmbedView(discord.ui.View):

    def __init__(self, author):
        super().__init__(timeout=None)
        self.author = author
        self.embed = None
        self.channel = None
        self.fields = []
        self.buttons = []
        self.role_ping = None

    def build_buttons(self):
        view = discord.ui.View()

        for b in self.buttons:
            view.add_item(discord.ui.Button(label=b["label"], url=b["url"]))

        return view

    # EDIT
    @discord.ui.button(label="✏️ Edit", style=discord.ButtonStyle.primary)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user != self.author:
            return await interaction.response.send_message("❌ Not your panel", ephemeral=True)

        await interaction.response.send_modal(EmbedModal(self))

    # ADD FIELD
    @discord.ui.button(label="➕ Field", style=discord.ButtonStyle.secondary)
    async def add_field(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user != self.author:
            return await interaction.response.send_message("❌ Not your panel", ephemeral=True)

        await interaction.response.send_modal(FieldModal(self))

    # ADD BUTTON
    @discord.ui.button(label="🔘 Button", style=discord.ButtonStyle.secondary)
    async def add_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user != self.author:
            return await interaction.response.send_message("❌ Not your panel", ephemeral=True)

        await interaction.response.send_modal(ButtonModal(self))

    # ROLE PING
    @discord.ui.button(label="📢 Ping Role", style=discord.ButtonStyle.secondary)
    async def ping_role(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user != self.author:
            return await interaction.response.send_message("❌ Not your panel", ephemeral=True)

        self.role_ping = interaction.user.top_role
        await interaction.response.send_message(f"✅ Will ping {self.role_ping.mention}", ephemeral=True)

    # SELECT CHANNEL
    @discord.ui.select(
        placeholder="Select channel...",
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text]
    )
    async def select_channel(self, interaction: discord.Interaction, select):

        if interaction.user != self.author:
            return await interaction.response.send_message("❌ Not yours", ephemeral=True)

        self.channel = select.values[0]

        await interaction.response.send_message(
            f"📍 Channel set: {self.channel.mention}",
            ephemeral=True
        )

    # SEND
    @discord.ui.button(label="📤 Send", style=discord.ButtonStyle.success)
    async def send(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user != self.author:
            return await interaction.response.send_message("❌ Not yours", ephemeral=True)

        if not self.embed or not self.channel:
            return await interaction.response.send_message("⚠️ Create embed & select channel", ephemeral=True)

        content = self.role_ping.mention if self.role_ping else None

        await self.channel.send(
            content=content,
            embed=self.embed,
            view=self.build_buttons() if self.buttons else None
        )

        await interaction.response.send_message("✅ Embed sent!", ephemeral=True)


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
            "📢 Ping role\n"
            "📤 Send when ready",
            view=view,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(EmbedBuilder(bot))
