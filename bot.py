import discord
from discord.ext import commands
import aiosqlite
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

DB_FILE = "patrols.db"

# ---------------- Events ----------------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# ---------------- Commands ----------------
@bot.command()
async def register(ctx, geofs_id: str, callsign: str):
    """Register your GeoFS ID + Callsign"""
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            INSERT OR REPLACE INTO users (discord_id, geofs_id, callsign)
            VALUES (?, ?, ?)""", (ctx.author.id, geofs_id, callsign))
        await db.commit()

    embed = discord.Embed(
        title="Registration Complete",
        description=f"Linked to GeoFS ID: **{geofs_id}**\nCallsign: **{callsign}**",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)


@bot.command()
async def on(ctx):
    """Start patrol"""
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("INSERT INTO patrols (discord_id) VALUES (?)", (ctx.author.id,))
        await db.commit()

    embed = discord.Embed(
        title="🛫 Patrol Started",
        description=f"{ctx.author.mention} is now **on patrol**",
        color=discord.Color.blue()
    )
    embed.add_field(name="Start Time", value=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))
    await ctx.send(embed=embed)


@bot.command()
async def off(ctx, aircraft: str, armament: str, status: str, base_takeoff: str, base_landed: str, *, notes: str = "None"):
    """End patrol with details"""
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
        """, (aircraft, armament, status, base_takeoff, base_landed, notes, ctx.author.id))
        await db.commit()

    embed = discord.Embed(
        title="🛬 Patrol Ended",
        description=f"{ctx.author.mention} has completed their patrol.",
        color=discord.Color.red()
    )
    embed.add_field(name="Aircraft", value=aircraft, inline=True)
    embed.add_field(name="Armament", value=armament, inline=True)
    embed.add_field(name="Status", value=status, inline=True)
    embed.add_field(name="Takeoff Base", value=base_takeoff, inline=True)
    embed.add_field(name="Landing Base", value=base_landed, inline=True)
    embed.add_field(name="Notes", value=notes, inline=False)
    embed.set_footer(text=datetime.utcnow().strftime("Ended at %Y-%m-%d %H:%M:%S UTC"))

    await ctx.send(embed=embed)

# ---------------- Run Bot ----------------
bot.run(TOKEN)
