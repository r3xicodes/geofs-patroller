import aiosqlite
import asyncio

async def setup():
    async with aiosqlite.connect("patrols.db") as db:
        # Users
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            discord_id INTEGER PRIMARY KEY,
            geofs_id TEXT NOT NULL,
            callsign TEXT NOT NULL
        )""")

        # Patrols
        await db.execute("""
        CREATE TABLE IF NOT EXISTS patrols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id INTEGER,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_time TIMESTAMP,
            aircraft TEXT,
            armament TEXT,
            status TEXT,
            base_takeoff TEXT,
            base_landed TEXT,
            notes TEXT,
            FOREIGN KEY (discord_id) REFERENCES users (discord_id)
        )""")

        await db.commit()

asyncio.run(setup())
print("✅ Database setup complete")
