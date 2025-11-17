# directory timesim.py

import random

# ---------------------------------------------------------------------------
# --- CORE CLOCK -------------------------------------------------------------
# ---------------------------------------------------------------------------

class WorldClock:
    """Keeps universal global (day) and local (hour) counters."""
    def __init__(self, start_day=0, start_hour=0, seed=None):
        self.global_tick = start_day    # days elapsed
        self.local_tick = start_hour    # hour of day (0–23)

        # NEW: attach per-clock RNG
        import random
        self.rng = random.Random(seed if seed is not None else 999999)

    def advance_local_tick(self):
        """Advance one hour; roll into next day every 24 ticks."""
        self.local_tick += 1
        if self.local_tick >= 24:
            self.local_tick = 0
            self.global_tick += 1

    def get_time(self):
        return {"day": self.global_tick, "hour": self.local_tick}

    def __repr__(self):
        return f"Day {self.global_tick}, {self.local_tick:02d}:00"


# ---------------------------------------------------------------------------
# --- REGION CLOCK -----------------------------------------------------------
# ---------------------------------------------------------------------------

class RegionClock:
    """
    A local clock synchronized to the global one but with a timezone offset.
    The offset can be positive (east, ahead) or negative (west, behind).
    """
    def __init__(self, name, offset_hours=0):
        self.name = name
        self.offset_hours = offset_hours
        self.local_hour = 0

    def update_from_global(self, global_hour):
        """Update this region's local hour from the global hour."""
        self.local_hour = (global_hour + self.offset_hours) % 24

    def __repr__(self):
        return f"{self.name}: {self.local_hour:02d}:00 (offset {self.offset_hours:+d})"


# ---------------------------------------------------------------------------
# --- TIME SYSTEM ------------------------------------------------------------
# ---------------------------------------------------------------------------

class TimeSystem:
    """
    Centralized world time manager that dispatches events.

    Event types:
      - 'local': every hour
      - 'global': once per day
      - int (e.g. 6, 12): every N hours
    Supports per-region timezones and local hourly context.
    """
    def __init__(self, start_day=0, start_hour=0):
        self.clock = WorldClock(start_day, start_hour)
        self.subscribers = {"local": [], "global": []}
        self.regions = []  # list[RegionClock]

    # --- Region management ---------------------------------------------------
    def add_region(self, name, offset_hours=0):
        rc = RegionClock(name, offset_hours)
        rc.update_from_global(self.clock.local_tick)
        self.regions.append(rc)
        return rc

    def get_region(self, name):
        for r in self.regions:
            if r.name == name:
                return r
        return None

    # --- Subscription interface ---------------------------------------------
    def subscribe(self, event_type, callback):
        """
        event_type: 'local', 'global', or integer interval (e.g. 6 for every 6 hours)
        callback(clock, region=None)
        """
        if event_type not in self.subscribers and not isinstance(event_type, int):
            raise ValueError("Invalid event_type. Use 'local', 'global', or integer interval.")
        self.subscribers.setdefault(event_type, []).append(callback)

    def subscribe_every(self, hours_interval, callback):
        """Run callback every N local hours."""
        self.subscribers.setdefault(hours_interval, []).append(callback)

    # --- Tick logic ----------------------------------------------------------
    def tick(self):
        """Advance one global hour, update all regions, and dispatch events."""
        self.clock.advance_local_tick()

        # Update all regional clocks
        for region in self.regions:
            region.update_from_global(self.clock.local_tick)

        # 1️⃣ Local (hourly) events
        for cb in self.subscribers.get("local", []):
            cb(self.clock, None)

        # 2️⃣ Interval events
        for interval, callbacks in self.subscribers.items():
            if isinstance(interval, int) and self.clock.local_tick % interval == 0:
                for cb in callbacks:
                    cb(self.clock, None)

        # 3️⃣ Global daily events
        if self.clock.local_tick == 0:
            for cb in self.subscribers.get("global", []):
                cb(self.clock, None)

    def run(self, hours=48):
        """Run the simulation for a given number of hours."""
        for _ in range(hours):
            self.tick()

def GetTimeState(hour):
    """
    Return a descriptive time-of-day state based on hour (0–23).
    Useful for NPC schedules, lighting, and narration.
    """
    if 4 <= hour < 6:
        return "dawn"
    elif 6 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 19:
        return "evening"
    elif 19 <= hour < 21:
        return "dusk"
    else:
        return "night"