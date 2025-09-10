import aiosqlite
import asyncio

DB_FILE = "patrols.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    discord_id TEXT PRIMARY KEY,
    geofs_id TEXT NOT NULL,
    callsign TEXT
);

CREATE TABLE IF NOT EXISTS patrols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT NOT NULL,
    geofs_id TEXT NOT NULL,
    callsign TEXT,
    start_time TEXT NOT NULL,
    end_time TEXT,
    aircraft TEXT,
    armaments TEXT,
    status TEXT,
    base_takeoff TEXT,
    base_landed TEXT,
    notes TEXT,
    active_seconds INTEGER DEFAULT 0
);
"""

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.executescript(SCHEMA)
        await db.commit()

if __name__ == "__main__":
    asyncio.run(init_db())
    print("[db_setup] Database initialized ✅")
