# directory event_manager.py/
from typing import Callable, List, Dict, Any
from timesim import TimeSystem
from tile_memory import SnapshotTileState
from world_utils import GetActiveTiles
from trade_routes import ApplyTradeEffects, GenerateTradeRoutes

class EventManager:
    """
    Global event orchestrator that connects TimeSystem ticks with simulation updates.
    Manages callbacks that modify tile, region, or economy data each tick.
    """

    def __init__(self, world, macro, time_system: TimeSystem):
        self.world = world
        self.macro = macro
        self.time_system = time_system
        self.global_events: List[Callable] = []
        self.hourly_events: List[Callable] = []
        self.interval_events: Dict[int, List[Callable]] = {}

    # --- Registration ------------------------------------------------------
    def register_global(self, callback: Callable):
        """Run once per in-game day."""
        self.global_events.append(callback)
        self.time_system.subscribe("global", self._wrap(callback))

    def register_hourly(self, callback: Callable):
        """Run every in-game hour."""
        self.hourly_events.append(callback)
        self.time_system.subscribe("local", self._wrap(callback))

    def register_interval(self, hours_interval: int, callback: Callable):
        """Run every N in-game hours."""
        self.interval_events.setdefault(hours_interval, []).append(callback)
        self.time_system.subscribe_every(hours_interval, self._wrap(callback))

    # --- Internal execution wrapper ---------------------------------------
    def _wrap(self, func):
        def wrapped(clock, region=None):
            # tick_id = f"{clock.global_tick}:{clock.local_tick:02d}"
            # fname = getattr(func, "__name__", repr(func))
            # print(f"[EventTick] {tick_id} → {fname}")
            func(self.world, self.macro, clock, region)
        return wrapped

    # --- Manual trigger (useful for testing) -------------------------------
    def trigger_all(self):
        """Run all registered event callbacks immediately."""
        for func in self.global_events + self.hourly_events:
            func(self.world, self.macro, self.time_system.clock, None)
        for interval, funcs in self.interval_events.items():
            for func in funcs:
                func(self.world, self.macro, self.time_system.clock, None)

def DailySettlementSnapshot(world, macro, clock, region=None):
    tick = clock.global_tick
    for tile in GetActiveTiles(world, "economy"):
        if tile.terrain == "settlement":
            SnapshotTileState(tile, tick)

def TickSettlements(world, macro, clock, region=None):
    import random
    # rng = random.Random(clock.global_tick * 100 + clock.local_tick)
    rng = clock.rng

    for tile in GetActiveTiles(world, "economy"):
        if tile.get_system("economy"):
            if rng.random() < 0.5:
                tile.agent.add_supplies(-0.5, 1)
            if rng.random() < 0.4:
                tile.agent.add_wealth(-0.5, 1)
            if rng.random() < 0.3:
                subs = tile.get_system("economy").get("sub_commodities", {})
                if subs:
                    cname = rng.choice(list(subs.keys()))
                    tile.agent.add_sub_commodity(0.5, cname)
