# directory main.py

import random
import sys
import math
import json
import curses
import matplotlib.pyplot as plt

from math import sqrt
from noise import pnoise2, pnoise3
from worldgen import *
from ecosystem import *
from behavior import *
from worldgen import *
from worldsim import *
from timesim import TimeSystem, GetTimeState
from economy import *
from event_manager import EventManager, DailySettlementSnapshot, TickSettlements
from tile_state import TileState
from world_index import WorldIndex
import world_index_store
from trade_routes import GenerateTradeRoutes, ApplyTradeEffects
from trade_visual import PrintTradeRoutes
from entities.update_all import UpdateAllEntities

# --- Global variables
world_time = 0

SYMBOLS = {
    "plains": "🌿",
    "forest": "🌳",
    "mountain": "⛰️",
    "settlement": "🏠",
    "riverside": "🏞️",
    "wetlands": "💦",
    "coastal": "🏖️",
    "deep_water": "🌊",
    "dryland": "🏜️",
    "oasis": "⛲",
    "river": "~"  # symbol for river overlay
}

def CreateWorld(world_time = None, master_seed = 12345):
    # Create a single deterministic RNG and pass it around
    rng = random.Random(master_seed)

    world = GenerateWorld(rng, width=20, height=20, num_continents=10, scale=15)
    world = AssignClimate(world, rng)
    # NEW: compute temperature + rainfall maps (deterministic)
    world = ComputeTemperatureAndRainfall(world, rng)

    world = AddDrylands(world, rng, num_dryspots=1, min_radius=3, max_radius=6)
    world = RefineDrylandBiomes(world, rng)

    # Use improved AddOases with deterministic rng
    world = AddOases(world, rng, chance_per_tile=0.1, max_cluster=1, require_full_surround=True, radius_check=1)
    world = DetectAndTagLakes(world)
    world = DeriveBiomeFromClimate(world)

    world, macro = DetectRegions(world)
    world = TagRivers(world, macro, max_rivers=25, seed=master_seed)
    macro = AssignRegionNames(macro, seed=master_seed)
    macro = AssignRegionTraits(macro, world, rng)  # 🧭 Add here
    world = MarkRegionLocalDirection(world, macro)

    world = PlaceSettlements(world, rng, min_distance=10, base_chance=0.3, density_scale=0.9)

    if world_time is None:
        world_time = 0
    world_time += 1

    # optional: if you run UpdateWeather immediately, recompute rainfall/temp again to incorporate humidity/wind
    # world = UpdateWeather(world, world_time)
    # world = ComputeTemperatureAndRainfall(world, rng)

    # --- IMPORTANT: some later passes modify terrain (oases, drylands, settlements).
    # Recompute soil + resource systems now that terrain is finalized.
    # This ensures resources reflect final tiles (used by InitializeSettlementEconomy).
    world = ComputeSoilAndResources(world, rng)

    world = SeedFloraFauna(world, rng)
    world = ConvertBiotaToCounts(world)
    world = InitializeEcosystemFromBiota(world, rng)

    world = InitializeSettlementEconomy(world, rng)
    AttachSettlementAgents(world)

    return world, macro

def PrintWorld(world):
    for row in world:
        symbols = []
        for tile in row:
            t = tile.terrain
            if t == "settlement":
                symbol = SYMBOLS["settlement"]
            elif tile.has_tag('river'):
                symbol = SYMBOLS["river"]
            else:
                symbol = SYMBOLS.get(t, "?")
            symbols.append(symbol)
        print(" ".join(symbols))

def PrintWorldWithCoords(world):
    width = len(world[0])
    print("    " + " ".join(f"{x:02}" for x in range(width)))

    for y, row in enumerate(world):
        row_symbols = []
        for tile in row:
            # --- Priority order ---
            t = tile.terrain
            if t == "settlement":
                symbol = SYMBOLS["settlement"]

            elif tile.has_tag("river_source"):
                symbol = "▲"
            elif tile.has_tag("river_mouth"):
                symbol = "▼"
            elif tile.has_tag("river"):
                symbol = "~"
            elif tile.has_tag("carved_valley"):
                symbol = "."
            elif tile.has_tag('river'):
                symbol = SYMBOLS["river"]
            else:
                symbol = SYMBOLS.get(t, "?")

            row_symbols.append(symbol)

        print(f"{y:02}  " + " ".join(row_symbols))

def hourly_event(clock, region):
    hour = clock.local_tick
    state = GetTimeState(hour)
    print(f"[{clock}] Time state: {state}")

def six_hour_event(clock, region):
    print(f"[{clock}] Every 6 hours event fired.")

def daily_event(clock, region):
    print(f"[{clock}] New day begins! Global update triggered.")

def regional_behavior(clock, region):
    print(f"  → {region.name} local time {region.local_hour:02d}:00")

# --- Main entry
def Main():
    master_seed = 2001
    # Deterministic master seed
    world, macro = CreateWorld(world_time = 0, master_seed = master_seed)
    # Build index
    world_index = WorldIndex(world)

    # Store into global access point
    world_index_store.world_index = world_index

    # Attach index into each tile
    for row in world:
        for tile in row:
            tile.index = world_index

    W = len(world[0])
    H = len(world)

    weather_noise = BuildNoiseGrid(W, H, master_seed + 10, scale=25.0, octaves=3)
    wind_noise = BuildNoiseGrid(W, H, master_seed + 20, scale=25.0, octaves=2)
    rain_noise = BuildNoiseGrid(W, H, master_seed + 30, scale=25.0, octaves=2)

    world_index_store.weather_noise = weather_noise
    world_index_store.wind_noise = wind_noise
    world_index_store.rain_noise = rain_noise

    trade_links = GenerateTradeRoutes(world)
    # store trade_links in tile (0,0) meta
    meta = world[0][0].get_system("meta")
    meta["trade_links"] = trade_links

    # PrintWorldWithCoords(world)
    PrintTradeRoutes(world, trade_links)
    # Create TimeSystem & EventManager
    time_system = TimeSystem(start_day=0, start_hour=6)
    event_manager = EventManager(world, macro, time_system)

    # Settlement AI
    event_manager.register_hourly(UpdateAllEntities)

    # Register economic and weather updates
    event_manager.register_global(lambda w, m, c, r: SimulateSettlementEconomy(w))
    event_manager.register_global(lambda w, m, c, r: UpdateWeather(w, c.global_tick))
    event_manager.register_interval(48, lambda w, m, c, r: SimulateEco(w, world_time=c.global_tick))
    event_manager.register_interval(48, lambda w, m, c, r: CheckAndTriggerEcoEvents(w, m, c.global_tick))

    def DailyTradeTick(world, macro, clock, region):
        ApplyTradeEffects(world)

    event_manager.register_global(DailyTradeTick)

    event_manager.register_global(DailySettlementSnapshot)

    print("Running 5 in-game days of economy simulation...\n")
    print("Global subscribers:", time_system.subscribers.get("global"))
    time_system.run(hours=2 * 24)
    print ("DONE")

    # PrintTradeRoutes(world, trade_links)

    ids = GetAllSettlementIDs(world)
    if not ids:
        print("⚠️ No settlements found — skipping economy inspection.")
        return
    print (ids)

    if ids:
        tile, econ = GetSettlementByID(world, ids[0])
        print("Tile tags:", tile.tags)
        for ent in tile.entities:
            if ent.type == "settlement_ai":
                print("Emotion:", ent.get("emotion").fear, ent.get("emotion").trust, ent.get("emotion").pride)
                print("Memory trend supplies:", ent.get("memory").detect_trend("supplies"))
                break

    # tile, econ = GetSettlementByID(world, ids[0])
    # print("Final settlement economy:", econ)
    # print("Tile from settlement:", tile)

    # tile = GetTile(world, 98, 16)
    # print("ACTUAL MEMORY SYSTEM:", tile.get_system("economy")) # Result None
    # print("ACTUAL MEMORY SYSTEM:", tile.get_system("memory")) # Result None
    # print("ACTUAL MEMORY SYSTEM:", tile.get_system("eco")) # {'producers': 602.1168973992137, 'herbivores': 36.76100517215208, 'carnivores': 3.7153955467983106, 'season': 'wet'}
    # print("ACTUAL MEMORY SYSTEM:", tile.get_system("weather")) # Result {'intensity': 0.609, 'state': 'rain'}
    # if tile:
    #     tile_dict = tile.to_dict()
    #     print(json.dumps(tile_dict, indent=2))
    # else:
    #     print("Out of bounds or empty tile")

    # eco = tile.get_system("eco")
    # print(
    #     f"Producers: {eco['producers']:.1f}, Herbivores: {eco['herbivores']:.1f}, Carnivores: {eco['carnivores']:.1f}")
    # print(
    #     f"Weather: {tile.get_system('weather')['state']}, Humidity: {tile.get_system('humidity')['current']}, Climate: {tile.climate}")
    #
    # region = GetRegionByTile(macro, 40, 47)
    # traits = region.get("region_traits", {})
    #
    # print (region)

    # targetRegion = GetRegionByTile(macro, 11, 79)
    # if targetRegion:
    #     print(targetRegion['id'], targetRegion['terrain'])
    #
    # west_tiles = GetRegionSectorTiles(world, macro, "continent", 1, "north")
    # print(f"Western sector of Continent #1: {len(west_tiles)} tiles")
    #
    # for r in macro["regions"]:
    #     print(f"[{r['terrain']:<16}] #{r['id']:>3} → {r['name']}")

    # time_system = TimeSystem(start_day=0, start_hour=20)

    # # Define regions with timezone offsets (east positive, west negative)
    # time_system.add_region("Eastern Isles", offset_hours=+3)
    # time_system.add_region("Central Empire", offset_hours=0)
    # time_system.add_region("Western Frontier", offset_hours=-4)

    # # Advance one hour
    # time_system.clock.advance_local_tick()
    #
    # # Advance multiple hours manually
    # for _ in range(6):
    #     time_system.clock.advance_local_tick()

    # Subscribe to events
    # time_system.subscribe("local", hourly_event)
    # time_system.subscribe_every(6, six_hour_event)
    # time_system.subscribe("global", daily_event)
    #
    # # Example: per-region hourly display
    # def update_regions(clock, _):
    #     for region in time_system.regions:
    #         regional_behavior(clock, region)
    #
    # time_system.subscribe("local", update_regions)
    #
    # # Run for two days (48 hours)
    # time_system.run(hours=48)

    # history = RunHistorySimulation(world, master_seed, steps = 365, sample_coords=(0, 59))
    # PlotEcosystemHistory(history)

# Execute Main
if __name__ == '__main__':
    Main()
