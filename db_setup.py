# db_setup.py

import aiosqlite
import asyncio

async def reset_db():
    async with aiosqlite.connect("patrols.db") as db:
        await db.execute("DROP TABLE IF EXISTS patrols")
        await db.execute("""
            CREATE TABLE patrols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT NOT NULL,
                geofs_id TEXT NOT NULL,
                callsign TEXT,
                start_time TEXT,
                end_time TEXT,
                aircraft TEXT,
                armaments TEXT,
                status TEXT,
                base_takeoff TEXT,
                base_landed TEXT,
                notes TEXT
            )
        """)
        await db.commit()
    print("✅ patrols table reset and created")

asyncio.run(reset_db())
