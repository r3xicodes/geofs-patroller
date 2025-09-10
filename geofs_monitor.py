import aiohttp
import asyncio
import aiosqlite
from datetime import datetime, timezone

DB_FILE = "patrols.db"
GEOFS_API_URL = "https://mps.geo-fs.com/map"


class GeoFSMonitor:
    def __init__(self):
        self.tracked = {}  # {discord_id: {...}}
        self.running = False

    async def poll(self):
        """Fetch live GeoFS players from multiplayer API."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(GEOFS_API_URL, timeout=10) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json()
                    return data.get("pilots", [])  # GeoFS map JSON
        except Exception as e:
            print(f"[monitor] Poll error: {e}")
            return []

    async def update_loop(self):
        self.running = True
        print("[monitor] background poll started")

        while self.running:
            players = await self.poll()
            seen_ids = {str(p.get("id")): p for p in players}

            now = datetime.utcnow().replace(tzinfo=timezone.utc).timestamp()

            for discord_id, info in list(self.tracked.items()):
                geofs_id = info["geofs_id"]
                pilot = seen_ids.get(str(geofs_id))

                if pilot:
                    speed = pilot.get("v", 0)  # velocity
                    if speed > 1:  # active flight
                        delta = now - info.get("last_seen", now)
                        info["active_seconds"] += int(delta)
                    info["last_seen"] = now
                else:
                    # pilot not seen, keep last_seen unchanged
                    pass

            await asyncio.sleep(30)  # poll every 30s

    def start_background(self, loop: asyncio.AbstractEventLoop):
        loop.create_task(self.update_loop())

    def stop(self):
        self.running = False
