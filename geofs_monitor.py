# geofs_monitor.py
import asyncio
import aiohttp
import aiosqlite
import time
from datetime import datetime

DB_FILE = "patrols.db"
# NOTE: This is the common community map endpoint used by many integrations.
# If your devs use a different endpoint, replace this URL and adjust JSON keys accordingly.
GEFS_MAP_URL = "https://mps.geo-fs.com/map"
POLL_INTERVAL = 60  # seconds

class GeoFSMonitor:
    def __init__(self):
        # tracked: discord_id -> session dict
        self.tracked = {}
        self._task = None
        self._running = False

    async def load_active_patrols_from_db(self):
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("""
                SELECT id, discord_id, geofs_id, start_time, active_seconds FROM patrols
                WHERE end_time IS NULL
            """) as cur:
                rows = await cur.fetchall()
            for row in rows:
                pid, discord_id, geofs_id, start_time, active_seconds = row
                self.tracked[str(discord_id)] = {
                    "geofs_id": str(geofs_id),
                    "patrol_id": pid,
                    "start_time": start_time,
                    "active_seconds": int(active_seconds or 0),
                    "last_seen": 0
                }
        print(f"[monitor] loaded {len(self.tracked)} active patrol(s) from DB")

    async def fetch_players(self, session):
        # fetch the GeoFS multiplayer map JSON
        async with session.get(GEFS_MAP_URL, timeout=30) as resp:
            if resp.status != 200:
                raise RuntimeError(f"GeoFS map fetch failed with status {resp.status}")
            return await resp.json()

    def find_player_index(self, players_json):
        """Return dict mapping geofs_id -> player object for quick lookup"""
        players_list = []
        if isinstance(players_json, dict) and "players" in players_json:
            players_list = players_json["players"]
        elif isinstance(players_json, list):
            players_list = players_json
        else:
            # unknown shape; try to use the dict as iterable of values
            try:
                players_list = list(players_json)
            except Exception:
                players_list = []

        index = {}
        for p in players_list:
            # Common key guesses: id, uid, userId, pid
            key = p.get("id") or p.get("uid") or p.get("userId") or p.get("pid")
            if key is not None:
                index[str(key)] = p
        return index

    def is_active(self, player):
        # This depends on the feed's field names.
        # Try multiple key names commonly found in community feeds.
        try:
            speed = player.get("speed") or player.get("v") or player.get("groundSpeed") or 0
            alt = player.get("alt") or player.get("altitude") or player.get("z") or 0
            # Convert to floats safely
            sp = float(speed or 0)
            al = float(alt or 0)
            # Criteria: moving OR above small altitude
            return (sp > 5.0) or (al > 5.0)
        except Exception:
            return False

    async def save_active_seconds(self, discord_id):
        s = self.tracked.get(str(discord_id))
        if not s:
            return
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("UPDATE patrols SET active_seconds = ? WHERE id = ?", (s["active_seconds"], s["patrol_id"]))
            await db.commit()

    async def poll_loop(self):
        await self.load_active_patrols_from_db()
        self._running = True
        async with aiohttp.ClientSession() as session:
            while self._running:
                try:
                    players = await self.fetch_players(session)
                except Exception as e:
                    print("[monitor] fetch error:", e)
                    await asyncio.sleep(10)
                    continue

                now_ts = time.time()
                index = self.find_player_index(players)

                # iterate tracked sessions
                for discord_id, sess in list(self.tracked.items()):
                    geofs_id = str(sess["geofs_id"])
                    player = index.get(geofs_id)
                    if player:
                        if self.is_active(player):
                            sess["active_seconds"] += POLL_INTERVAL
                            sess["last_seen"] = now_ts
                            # update callsign if feed provides a label/name
                            callsign = player.get("callsign") or player.get("label") or player.get("name")
                            if callsign:
                                # update patrols.callsign for this patrol id
                                async with aiosqlite.connect(DB_FILE) as db:
                                    await db.execute("UPDATE patrols SET callsign = ? WHERE id = ?", (callsign, sess["patrol_id"]))
                                    await db.commit()
                            # periodically persist (every 5 min of active seconds)
                            if sess["active_seconds"] % 300 == 0:
                                await self.save_active_seconds(discord_id)
                        else:
                            # present but idle -> do nothing
                            pass
                    else:
                        # not present -> do nothing
                        pass

                await asyncio.sleep(POLL_INTERVAL)

    def start_background(self, loop):
        if self._task is None:
            self._task = loop.create_task(self.poll_loop())
            print("[monitor] background poll started")

    def stop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        print("[monitor] stopped")
