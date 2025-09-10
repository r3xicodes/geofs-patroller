import os
import aiosqlite
import discord
from discord import app_commands
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from geofs_monitor import GeoFSMonitor, DB_FILE
import asyncio

# ---------------- Setup ----------------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # optional

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not set in .env")


class PatrolBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.monitor = GeoFSMonitor()

    async def setup_hook(self):
        guild = None
        if GUILD_ID:
            try:
                gid = int(GUILD_ID)
                guild = discord.Object(id=gid)
            except Exception:
                print("[bot] Invalid GUILD_ID in .env")

        if guild:
            # Clear old commands before resync
            self.tree.clear_commands(guild=guild)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            print(f"[bot] Force-synced {len(synced)} commands to guild {guild.id}")
        else:
            self.tree.clear_commands()
            synced = await self.tree.sync()
            print(f"[bot] Force-synced {len(synced)} global commands")

        loop = asyncio.get_running_loop()
        self.monitor.start_background(loop)

    async def on_ready(self):
        print(f"[bot] Logged in as {self.user} (id: {self.user.id})")


bot = PatrolBot()

# ---------------- Commands ----------------


@bot.tree.command(name="register", description="Register your GeoFS ID and optional callsign")
async def register(interaction: discord.Interaction, geofs_id: str, callsign: str = None):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (discord_id, geofs_id, callsign) VALUES (?, ?, ?)",
            (str(interaction.user.id), str(geofs_id), callsign),
        )
        await db.commit()
    await interaction.response.send_message(
        f"✅ Linked GeoFS ID `{geofs_id}` to {interaction.user.mention}", ephemeral=True
    )


@bot.tree.command(name="on", description="Start a patrol")
async def on_cmd(interaction: discord.Interaction):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(
            "SELECT geofs_id, callsign FROM users WHERE discord_id = ?",
            (str(interaction.user.id),),
        ) as cur:
            row = await cur.fetchone()

    if not row:
        return await interaction.response.send_message(
            "⚠️ You must `/register` first with your GeoFS ID.", ephemeral=True
        )

    geofs_id, callsign = row
    start_time = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute(
            "INSERT INTO patrols (discord_id, geofs_id, callsign, start_time) VALUES (?, ?, ?, ?)",
            (str(interaction.user.id), str(geofs_id), callsign, start_time),
        )
        await db.commit()
        patrol_id = cur.lastrowid

    bot.monitor.tracked[str(interaction.user.id)] = {
        "geofs_id": str(geofs_id),
        "patrol_id": patrol_id,
        "start_time": start_time,
        "active_seconds": 0,
        "last_seen": 0,
    }

    embed = discord.Embed(title="🛫 Patrol Started", color=discord.Color.blue())
    embed.add_field(name="Pilot", value=interaction.user.mention, inline=True)
    embed.add_field(name="Callsign", value=callsign or "—", inline=True)
    embed.add_field(name="Start (UTC)", value=start_time, inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="off", description="End your patrol")
async def off_cmd(
    interaction: discord.Interaction,
    aircraft: str,
    armaments: str,
    status: str,
    base_takeoff: str,
    base_landed: str,
    notes: str = "",
):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(
            "SELECT id, start_time, active_seconds, callsign FROM patrols WHERE discord_id = ? AND end_time IS NULL",
            (str(interaction.user.id),),
        ) as cur:
            row = await cur.fetchone()

    if not row:
        return await interaction.response.send_message(
            "⚠️ No active patrol found. Use `/on` first.", ephemeral=True
        )

    pid, start_time, active_seconds, callsign = row
    end_time = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            """UPDATE patrols SET end_time=?, aircraft=?, armaments=?, status=?, base_takeoff=?, base_landed=?, notes=? WHERE id=?""",
            (end_time, aircraft, armaments, status, base_takeoff, base_landed, notes, pid),
        )
        await db.commit()

    tracked = bot.monitor.tracked.pop(str(interaction.user.id), None)
    total_seconds = tracked.get("active_seconds", 0) if tracked else int(active_seconds or 0)

    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE patrols SET active_seconds = ? WHERE id = ?", (total_seconds, pid))
        await db.commit()

    secs = int(total_seconds or 0)
    mins = secs // 60
    hours = mins // 60
    mins = mins % 60
    dur_str = f"{hours}h {mins}m" if hours else f"{mins}m"

    embed = discord.Embed(title="🛬 Patrol Completed", color=discord.Color.red())
    embed.add_field(name="Pilot", value=interaction.user.mention, inline=True)
    embed.add_field(name="Callsign", value=callsign or "—", inline=True)
    embed.add_field(name="Aircraft", value=aircraft, inline=True)
    embed.add_field(name="Armaments", value=armaments, inline=True)
    embed.add_field(name="Status", value=status, inline=True)
    embed.add_field(name="Takeoff", value=base_takeoff, inline=True)
    embed.add_field(name="Landing", value=base_landed, inline=True)
    embed.add_field(name="Active Flight Time", value=dur_str, inline=False)
    if notes:
        embed.add_field(name="Notes", value=notes, inline=False)
    embed.set_footer(text=f"Ended (UTC): {end_time}")

    if status.lower() == "dead":
        respawn = (datetime.utcnow() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S UTC")
        embed.add_field(name="Respawn Available", value=respawn, inline=False)

    await interaction.response.send_message(embed=embed)


try:
    bot.run(TOKEN)
except KeyboardInterrupt:
    print("[bot] Shutting down")
    bot.monitor.stop()
