import discord
from discord import app_commands
import aiosqlite
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

class GeoFSPatrolBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # Sync commands to Discord
        await self.tree.sync()
        print("✅ Slash commands synced.")

bot = GeoFSPatrolBot()
DB_FILE = "patrols.db"

# ---------------- Slash Commands ----------------

@bot.tree.command(name="register", description="Register your GeoFS ID and callsign")
async def register(interaction: discord.Interaction, geofs_id: str, callsign: str):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users (discord_id, geofs_id, callsign)
            VALUES (?, ?, ?)""", (interaction.user.id, geofs_id, callsign))
        await db.commit()

    embed = discord.Embed(
        title="Registration Complete",
        description=f"GeoFS ID: **{geofs_id}**\nCallsign: **{callsign}**",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="on", description="Start a patrol")
async def on(interaction: discord.Interaction):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("INSERT INTO patrols (discord_id) VALUES (?)", (interaction.user.id,))
        await db.commit()

    embed = discord.Embed(
        title="🛫 Patrol Started",
        description=f"{interaction.user.mention} is now **on patrol**",
        color=discord.Color.blue()
    )
    embed.add_field(name="Start Time", value=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="off", description="End a patrol with details")
async def off(interaction: discord.Interaction,
              aircraft: str,
              armament: str,
              status: str,
              base_takeoff: str,
              base_landed: str,
              notes: str = "None"):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            UPDATE patrols
            SET end_time = CURRENT_TIMESTAMP,
                aircraft = ?,
                armament = ?,
                status = ?,
                base_takeoff = ?,
                base_landed = ?,
                notes = ?
            WHERE discord_id = ? AND end_time IS NULL
        """, (aircraft, armament, status, base_takeoff, base_landed, notes, interaction.user.id))
        await db.commit()

    embed = discord.Embed(
        title="🛬 Patrol Ended",
        description=f"{interaction.user.mention} has completed their patrol.",
        color=discord.Color.red()
    )
    embed.add_field(name="Aircraft", value=aircraft, inline=True)
    embed.add_field(name="Armament", value=armament, inline=True)
    embed.add_field(name="Status", value=status, inline=True)
    embed.add_field(name="Takeoff Base", value=base_takeoff, inline=True)
    embed.add_field(name="Landing Base", value=base_landed, inline=True)
    embed.add_field(name="Notes", value=notes, inline=False)
    embed.set_footer(text=datetime.utcnow().strftime("Ended at %Y-%m-%d %H:%M:%S UTC"))

    await interaction.response.send_message(embed=embed)

# ---------------- Run ----------------
bot.run(TOKEN)
