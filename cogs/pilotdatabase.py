# pilotdatabase.py

import discord
from discord import app_commands
from discord.ext import commands
import os
from supabase import create_client, Client

# Initialize Supabase
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

class PilotDatabase(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(
        name="pilotdatabase_penal",
        description="Send the pilot database embed with buttons (Executive only)"
    )
    @app_commands.default_permissions()
    async def pilotdatabase_penal(self, interaction: discord.Interaction):
        # Check if user has executive role
        executive_role_id = 1389824452778262589
        executive_role = interaction.guild.get_role(executive_role_id)
        
        if executive_role not in interaction.user.roles:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to use this command.\n*Executive Team only*",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Get pilot count
        pilot_count = await self.get_pilot_count()
        
        # Create the main embed
        embed = discord.Embed(
            title="✈️ Pilot Database",
            description="Welcome to the **Pilot Database**!\n\nUse the buttons below to search, add, or manage pilot records.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📋 Database Info",
            value=f"• **Total Pilots:** `{pilot_count}`\n• **Last Updated:** <t:{int(discord.utils.utcnow().timestamp())}:R>",
            inline=False
        )
        
        embed.add_field(
            name="🔍 How to Use",
            value="• Click **Search Pilot** to find a pilot\n• Click **Add Pilot** to add new records\n• Click **All Pilots** to view the full list",
            inline=False
        )
        
        embed.set_footer(text="Pilot Database System • Executive Access Only")
        if interaction.guild and interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        
        # Create buttons - Pass supabase to the view
        view = PilotDatabaseView(supabase)
        
        await interaction.response.send_message(embed=embed, view=view)
    
    async def get_pilot_count(self):
        try:
            response = supabase.table("pilots").select("*", count="exact").execute()
            return response.count if hasattr(response, 'count') else len(response.data)
        except Exception as e:
            print(f"Error getting pilot count: {e}")
            return 0

class PilotDatabaseView(discord.ui.View):
    def __init__(self, supabase_client):
        super().__init__(timeout=None)
        self.supabase = supabase_client  # Store supabase client as instance variable
    
    @discord.ui.button(
        label="🔍 Search Pilot",
        style=discord.ButtonStyle.primary,
        custom_id="search_pilot"
    )
    async def search_pilot_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SearchPilotModal(self.supabase)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="➕ Add Pilot",
        style=discord.ButtonStyle.success,
        custom_id="add_pilot"
    )
    async def add_pilot_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddPilotModal(self.supabase)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="📋 All Pilots",
        style=discord.ButtonStyle.secondary,
        custom_id="all_pilots"
    )
    async def all_pilots_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_all_pilots(interaction)
    
    async def show_all_pilots(self, interaction: discord.Interaction):
        try:
            response = self.supabase.table("pilots").select("*").execute()
            pilots = response.data
            
            if not pilots:
                embed = discord.Embed(
                    title="📋 All Pilots",
                    description="No pilots found in the database.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Create paginated pages (6 pilots per page for better formatting)
            pages = []
            page_count = (len(pilots) - 1) // 6 + 1
            
            for i in range(0, len(pilots), 6):
                page_num = i // 6 + 1
                page_pilots = pilots[i:i+6]
                embed = discord.Embed(
                    title="📋 All Pilots",
                    description=f"Page {page_num}/{page_count} • Total: {len(pilots)} pilots",
                    color=discord.Color.blue()
                )
                
                for pilot in page_pilots:
                    embed.add_field(
                        name=f"✈️ {pilot.get('callsign', 'Unknown')}",
                        value=f"**Name:** {pilot.get('name', 'N/A')}\n**Rating:** {pilot.get('rating', 'N/A')}\n**Hours:** {pilot.get('hours', 0)}",
                        inline=True
                    )
                
                pages.append(embed)
            
            # Send first page with pagination
            view = PaginationView(pages, 0, self.supabase)
            await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to fetch pilots: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class SearchPilotModal(discord.ui.Modal, title="Search Pilot"):
    def __init__(self, supabase_client):
        super().__init__()
        self.supabase = supabase_client
    
    search_query = discord.ui.TextInput(
        label="Search by Callsign or Name",
        placeholder="Enter callsign or pilot name...",
        style=discord.TextStyle.short,
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        query = self.search_query.value.lower()
        
        try:
            # Search in database
            response = self.supabase.table("pilots")\
                .select("*")\
                .or_(f"callsign.ilike.%{query}%,name.ilike.%{query}%")\
                .execute()
            
            results = response.data
            
            if not results:
                embed = discord.Embed(
                    title="🔍 Search Results",
                    description=f"No pilots found matching: **{query}**",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Create results embed
            embed = discord.Embed(
                title="🔍 Search Results",
                description=f"Found **{len(results)}** pilot(s) matching: **{query}**",
                color=discord.Color.green()
            )
            
            for pilot in results[:5]:  # Limit to 5 results
                embed.add_field(
                    name=f"✈️ {pilot.get('callsign', 'Unknown')}",
                    value=f"**Name:** {pilot.get('name', 'N/A')}\n**Rating:** {pilot.get('rating', 'N/A')}\n**Hours:** {pilot.get('hours', 0)}",
                    inline=False
                )
            
            if len(results) > 5:
                embed.set_footer(text=f"Showing 5 of {len(results)} results")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Search failed: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class AddPilotModal(discord.ui.Modal, title="Add New Pilot"):
    def __init__(self, supabase_client):
        super().__init__()
        self.supabase = supabase_client
    
    callsign = discord.ui.TextInput(
        label="Callsign",
        placeholder="e.g., SPEED01",
        style=discord.TextStyle.short,
        required=True,
        max_length=10
    )
    
    name = discord.ui.TextInput(
        label="Pilot Name",
        placeholder="e.g., John Smith",
        style=discord.TextStyle.short,
        required=True,
        max_length=100
    )
    
    rating = discord.ui.TextInput(
        label="Rating",
        placeholder="e.g., Captain, First Officer",
        style=discord.TextStyle.short,
        required=True,
        max_length=50
    )
    
    hours = discord.ui.TextInput(
        label="Flight Hours",
        placeholder="e.g., 1500",
        style=discord.TextStyle.short,
        required=True,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            pilot_data = {
                "callsign": self.callsign.value.upper(),
                "name": self.name.value,
                "rating": self.rating.value,
                "hours": int(self.hours.value),
                "added_by": interaction.user.id,
                "added_at": discord.utils.utcnow().isoformat()
            }
            
            # Insert into Supabase
            response = self.supabase.table("pilots").insert(pilot_data).execute()
            
            embed = discord.Embed(
                title="✅ Pilot Added Successfully!",
                description=f"**Callsign:** {pilot_data['callsign']}\n**Name:** {pilot_data['name']}\n**Rating:** {pilot_data['rating']}\n**Hours:** {pilot_data['hours']}",
                color=discord.Color.green()
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to add pilot: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class PaginationView(discord.ui.View):
    def __init__(self, pages, current_page=0, supabase_client=None):
        super().__init__(timeout=60)
        self.pages = pages
        self.current_page = current_page
        self.supabase = supabase_client
        
        # Update button states
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.pages) - 1
    
    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        await self.update_message(interaction)
    
    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        await self.update_message(interaction)
    
    async def update_message(self, interaction: discord.Interaction):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.pages) - 1
        
        await interaction.response.edit_message(
            embed=self.pages[self.current_page],
            view=self
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(PilotDatabase(bot))
