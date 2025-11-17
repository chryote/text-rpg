# directory mock_simulation_plotting.py

import matplotlib.pyplot as plt
from random import Random
from main import CreateWorld
from economy import GetAllSettlementIDs, GetSettlementByID, SimulateSettlementEconomy, SettlementEconomyAgent, RandomSettlementPerturbation
from worldgen import UpdateWeather, BuildNoiseGrid
from timesim import TimeSystem
from event_manager import EventManager, TickSettlements
from tile_events import TriggerTileEvents, TriggerEventFromLibrary, ScheduleTileEvent

# --- Simulation setup -------------------------------------------------------

import matplotlib.pyplot as plt
from economy import GetAllSettlementIDs, GetSettlementByID
from world_index import WorldIndex
import world_index_store
from trade_routes import GenerateTradeRoutes, ApplyTradeEffects

def PlotSettlementInteractionOverTime(world, macro, time_system, days=5):
    """
    Visualize interactions by plotting each settlement's WEALTH
    over time as trade + economy tick runs.
    """

    from economy import GetAllSettlementIDs, GetSettlementByID
    from trade_routes import GenerateTradeRoutes, ApplyTradeEffects

    settlement_ids = GetAllSettlementIDs(world)
    history = {sid: [] for sid in settlement_ids}
    ticks = []

    # create trade routes once
    trade_links = GenerateTradeRoutes(world)

    total_hours = days * 24
    for _ in range(total_hours):

        # tick the time system (this also triggers economy + events)
        time_system.tick()

        # apply trade effects once per day (when hour == 0)
        if time_system.clock.local_tick == 0:
            ApplyTradeEffects(world, trade_links)

        # record wealth over time
        ticks.append(time_system.clock.global_tick * 24 + time_system.clock.local_tick)

        for sid in settlement_ids:
            tile, econ = GetSettlementByID(world, sid)
            if econ:
                history[sid].append(econ["wealth"])
            else:
                history[sid].append(None)

    # ---- Plot ----
    plt.figure(figsize=(12, 6))
    for sid, values in history.items():
        plt.plot(ticks, values, label=f"Settlement {sid}", linewidth=1.2)

    plt.title("Settlement Wealth Over Time — Trade Interaction Visualization")
    plt.xlabel("Ticks (hours)")
    plt.ylabel("Wealth")
    plt.grid(True, alpha=0.3)
    plt.legend(ncol=3, fontsize=7)
    plt.tight_layout()
    plt.show()

    return history, ticks


def RunSingleSettlementEconomySimulation(days=5, master_seed=2001):
    rng = Random(master_seed)

    # Create world + macro structure
    world, macro = CreateWorld(world_time=0, master_seed=master_seed)

    settlement_ids = GetAllSettlementIDs(world)
    # target_id = settlement_ids[0]  # choose the first settlement (or any specific ID)
    target_id = 6871  # choose the first settlement (or any specific ID)
    tile, econ = GetSettlementByID(world, target_id)
    print(f"Tracking {econ['name']} (ID {target_id})\n")

    # Prepare time system
    time_system = TimeSystem(start_day=0, start_hour=6)
    event_manager = EventManager(world, macro, time_system)

    # Record per-hour data
    history = {"supplies": [], "wealth": [], "subs": {}}
    ticks = []

    # Register economy and weather updates
    event_manager.register_global(lambda w, m, c, r: SimulateSettlementEconomy(w, rng))
    event_manager.register_interval(6, lambda w, m, c, r: UpdateWeather(w, c.global_tick))
    event_manager.register_interval(1, RandomSettlementPerturbation)
    # event_manager.register_interval(1, TickSettlements)

    # Run TriggerTileEvents ONCE!
    event_manager.register_interval(1, TriggerTileEvents)

    # Run TriggerEvent when condition is right, for now its just testing on first tick
    TriggerEventFromLibrary(tile, "market_boom")
    TriggerEventFromLibrary(tile, "festival")

    # Example: start a drought 5 days (ticks) from now
    current_tick = time_system.clock.global_tick
    ScheduleTileEvent(tile, "drought", start_tick=current_tick + 2)

    # Local (hourly) event to record economy
    def record_settlement(clock, region=None):
        ticks.append(clock.global_tick * 24 + clock.local_tick)
        _, econ = GetSettlementByID(world, target_id)

        # record main stats
        history["supplies"].append(econ["supplies"])
        history["wealth"].append(econ["wealth"])

        # record each sub-commodity
        for name, value in econ["sub_commodities"].items():
            history["subs"].setdefault(name, []).append(value)

    time_system.subscribe("local", record_settlement)

    # --- Run simulation (5 days = 120 hours) ---
    hours = days * 24
    print(f"Running {days} in-game days ({hours} hours)...")
    time_system.run(hours=hours)

    return history, ticks, world, econ

def RunSettlementEconomySimulation(days=5, master_seed=2001):
    rng = Random(master_seed)

    # Create world + macro structure
    world, macro = CreateWorld(world_time=0, master_seed=master_seed)

    # Prepare time system
    time_system = TimeSystem(start_day=0, start_hour=6)
    event_manager = EventManager(world, macro, time_system)

    # Record per-hour data
    settlement_ids = GetAllSettlementIDs(world)
    history = {vid: [] for vid in settlement_ids}
    ticks = []

    # Register economy and weather updates
    event_manager.register_global(lambda w, m, c, r: SimulateSettlementEconomy(w, rng))
    event_manager.register_interval(6, lambda w, m, c, r: UpdateWeather(w, c.global_tick))
    event_manager.register_interval(1, RandomSettlementPerturbation)
    # event_manager.register_interval(1, TickSettlements)

    # Local (hourly) event to record economy
    def record_supplies(clock, region=None):
        ticks.append(clock.global_tick * 24 + clock.local_tick)
        for vid in settlement_ids:
            _, econ = GetSettlementByID(world, vid)
            history[vid].append(econ["supplies"])

    time_system.subscribe("local", record_supplies)

    # --- Run simulation (5 days = 120 hours) ---
    hours = days * 24
    print(f"Running {days} in-game days ({hours} hours)...")
    time_system.run(hours=hours)

    return history, ticks, world


# --- Plotting ---------------------------------------------------------------

def PlotSettlementSupplies(history, ticks):
    plt.figure(figsize=(10, 6))
    for vid, supplies in history.items():
        plt.plot(ticks, supplies, label=f"Settlement {vid}")

    plt.title("Settlement Supplies Evolution Over 5 In-Game Days")
    plt.xlabel("Local Tick (hours)")
    plt.ylabel("Supplies")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

def PlotSingleSettlementEconomy(history, ticks, econ_name):
    plt.figure(figsize=(10, 6))
    plt.subplot(2, 1, 1)
    plt.plot(ticks, history["supplies"], label="Supplies")
    plt.plot(ticks, history["wealth"], label="Wealth")
    plt.title(f"{econ_name} — Economy over Time")
    plt.xlabel("Local Tick (hours)")
    plt.ylabel("Value")
    plt.legend()
    plt.grid(True)

    plt.subplot(2, 1, 2)
    for cname, values in history["subs"].items():
        plt.plot(ticks, values, label=cname)
    plt.xlabel("Local Tick (hours)")
    plt.ylabel("Sub-Commodities")
    plt.legend()
    plt.grid(True)

    plt.tight_layout()
    plt.show()

def RankVillageTypes(world, trade_links):
    """
    Summarize economic performance by settlement tag types.
    Produces ranking of TAG → trade volume, supplies, wealth.
    """

    from economy import GetAllSettlementIDs, GetSettlementByID

    # Tags we consider meaningful for village types
    TAG_GROUPS = [
        "prosperous",
        "struggling",
        "supplies_deficit",
        "trade_hub",
        "bandit_settlement",
    ]

    tag_data = {tag: {"count": 0, "total_trade": 0.0, "total_supplies": 0.0, "total_wealth": 0.0}
                for tag in TAG_GROUPS}

    sids = GetAllSettlementIDs(world)

    for sid in sids:
        tile, econ = GetSettlementByID(world, sid)
        if not econ:
            continue

        # compute trade volume for this settlement
        routes = trade_links.get(sid, [])
        trade_volume = sum(r["value"] for r in routes)

        # find tags this village has
        for tag in TAG_GROUPS:
            if tile.has_tag(tag):

                tag_data[tag]["count"] += 1
                tag_data[tag]["total_trade"] += trade_volume
                tag_data[tag]["total_supplies"] += econ["supplies"]
                tag_data[tag]["total_wealth"] += econ["wealth"]

    # build ranked summary
    summary = []
    for tag, data in tag_data.items():
        if data["count"] == 0:
            continue

        summary.append({
            "tag": tag,
            "count": data["count"],
            "avg_trade": data["total_trade"] / data["count"],
            "avg_supplies": data["total_supplies"] / data["count"],
            "avg_wealth": data["total_wealth"] / data["count"],
        })

    # sort descending by avg_trade
    summary.sort(key=lambda r: r["avg_trade"], reverse=True)

    # print nicely
    print("\n=== Village Type Performance Ranking ===")
    print("Tag Type           Cnt   AvgTrade   AvgSupplies   AvgWealth")
    print("-------------------------------------------------------------")

    for s in summary:
        print(f"{s['tag']:15s}  {s['count']:3d}  "
              f"{s['avg_trade']:10.2f}  "
              f"{s['avg_supplies']:12.2f}  "
              f"{s['avg_wealth']:10.2f}")

    return summary



# --- Entry Point ------------------------------------------------------------

if __name__ == "__main__":

    master_seed = 2001

    # --- 1) Create TimeSystem for interaction simulation ---
    from timesim import TimeSystem
    time_system = TimeSystem(start_day=0, start_hour=6)

    # --- 2) Generate world + macro (needed for regions & trade routes) ---
    from main import CreateWorld
    world, macro = CreateWorld(world_time=0, master_seed=master_seed)

    # --- 3) Build world index ---
    from world_index import WorldIndex
    import world_index_store

    world_index = WorldIndex(world)
    world_index_store.world_index = world_index

    # Attach index to each tile
    for row in world:
        for tile in row:
            tile.index = world_index

    # --- 4) Inject weather noise (needed before UpdateWeather) ---
    from worldgen import BuildNoiseGrid

    W = len(world[0])
    H = len(world)

    world_index_store.weather_noise = BuildNoiseGrid(W, H, master_seed + 10, scale=25.0, octaves=3)
    world_index_store.wind_noise    = BuildNoiseGrid(W, H, master_seed + 20, scale=25.0, octaves=2)
    world_index_store.rain_noise    = BuildNoiseGrid(W, H, master_seed + 30, scale=25.0, octaves=2)

    # --- 5) Plot interaction over time (new visualization) ---
    history_interact, ticks_interact = PlotSettlementInteractionOverTime(
        world, macro, time_system, days=60
    )

    # --- 6) Generate trade routes for ranking analysis ---
    from trade_routes import GenerateTradeRoutes
    trade_links = GenerateTradeRoutes(world)

    # --- 7) Rank by village type (prosperous / supplies_deficit / trade_hub / bandit) ---
    RankVillageTypes(world, trade_links)

    # (Optional) If you want to also run the single settlement sim:
    # history, ticks, world_single, econ = RunSingleSettlementEconomySimulation(days=5)
    # PlotSingleSettlementEconomy(history, ticks, econ)
