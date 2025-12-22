# directory main.py

import random
import sys
import math
import json
import curses
import matplotlib.pyplot as plt

from math import sqrt
from noise import pnoise2, pnoise3

from world_utils import SaveWorldStateToMeta, PrintWorldWithCoords, PrintWorld
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
from trade_routes import GenerateTradeRoutes, ApplyTradeEffects, UpdateTradeRouteRisks, UpdateTradeNetwork
from trade_visual import PrintTradeRoutes, RenderTradeRouteMap
from entities.update_all import UpdateAllEntities
from world_state_director import DirectorController
from world_utils import MeasureSimulationSpeed

# --- Global variables
world_time = 0

def CreateWorld(world_time = None, master_seed = 12345):
    # Create a single deterministic RNG and pass it around
    rng = random.Random(master_seed)

    world = GenerateWorld(rng, width=100, height=100, num_continents=10, scale=15)
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

    # Calculate and attach geo_pressure for NPC tendency forming
    world = ComputeGeoPressure(world, rng)

    world = SeedFloraFauna(world, rng)
    world = ConvertBiotaToCounts(world)
    world = InitializeEcosystemFromBiota(world, rng)

    world = InitializeSettlementEconomy(world, rng)
    AttachSettlementAgents(world)

    return world, macro

# --- Main entry
def Main():
    director = DirectorController()
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

    PrintWorld(world)
    # PrintTradeRoutes(world, trade_links)
    # RenderTradeRouteMap(world, trade_links, tile_size=24, filename="routes.png")
    # Create TimeSystem & EventManager
    time_system = TimeSystem(start_day=0, start_hour=0)
    event_manager = EventManager(world, macro, time_system)

    # Settlement AI
    event_manager.register_hourly(UpdateAllEntities)

    # Register economic and weather updates
    event_manager.register_global(lambda world, macro, time, rng, director=director: SimulateSettlementEconomy(world, director))
    event_manager.register_global(lambda w, m, c, r: UpdateWeather(w, c.global_tick))
    event_manager.register_interval(48, lambda w, m, c, r: SimulateEco(w, world_time=c.global_tick))
    event_manager.register_interval(48, lambda w, m, c, r: CheckAndTriggerEcoEvents(w, m, c.global_tick))

    def DailyTradeTick(world, macro, clock, region):
        # 1. Update Risks BEFORE applying effects
        UpdateTradeRouteRisks(world)  # <<-- NEW: Recalculate risk

        ApplyTradeEffects(world)

    event_manager.register_global(DailyTradeTick)
    event_manager.register_global(DailySettlementSnapshot)
    event_manager.register_interval(168, UpdateTradeNetwork)

    event_manager.register_global(lambda w, m, c, r: director.update(c.global_tick))
    event_manager.register_global(lambda w, m, c, r: SaveWorldStateToMeta(w, director))

    print("Running 5 in-game days of economy simulation...\n")
    print("Global subscribers:", time_system.subscribers.get("global"))

    # Example usage in Main()
    # Measure 1 hour of full world simulation
    seconds_per_hour = MeasureSimulationSpeed(time_system, hours_to_run=24)

    # Estimate how long 24 hours (1 day) will take
    estimated_day_time = seconds_per_hour * 24
    print(f"Estimated time for 1 in-game day: {estimated_day_time:.2f} seconds")

    # time_system.run(hours=1 * 1)
    print ("DONE")

    meta_tile = world[0][0]
    meta = meta_tile.get_system("meta")

    print (meta['world_state'])

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

    tile = GetTile(world, 19, 0)
    # print("ACTUAL MEMORY SYSTEM:", tile.get_system("economy")) # Result None
    # print("ACTUAL MEMORY SYSTEM:", tile.get_system("memory")) # Result None
    # print("ACTUAL MEMORY SYSTEM:", tile.get_system("eco")) # {'producers': 602.1168973992137, 'herbivores': 36.76100517215208, 'carnivores': 3.7153955467983106, 'season': 'wet'}
    # print("ACTUAL MEMORY SYSTEM:", tile.get_system("weather")) # Result {'intensity': 0.609, 'state': 'rain'}
    if tile:
        tile_dict = tile.to_dict()
        print(json.dumps(tile_dict, indent=2))
    else:
        print("Out of bounds or empty tile")

# Execute Main
if __name__ == '__main__':
    Main()
