# directory worldsim.py

import random
import math
import matplotlib.pyplot as plt

from worldgen import GetNeighbors
from world_utils import GetActiveTiles
from ecosystem import *

# Wind directions (8 cardinal + diagonal)
WIND_DIRECTIONS = [
    (0, -1, "north"),
    (1, -1, "northeast"),
    (1, 0, "east"),
    (1, 1, "southeast"),
    (0, 1, "south"),
    (-1, 1, "southwest"),
    (-1, 0, "west"),
    (-1, -1, "northwest"),
]

def SimulateTrophicEcosystem(world, rng = None, world_time = 0, dt = 1.0):
    """
    Ecosystem simulation with seasonal variation and neighbor diffusion.
    Produces perpetual oscillations via time-varying growth and mortality.
    """

    print ("SIMULATING ECOSYSTEM...")

    if isinstance(rng, int):
        import random
        rng = random.Random(rng)
    elif rng is None:
        import random
        rng = random.Random()

    for tile in GetActiveTiles(world, "eco"):
        eco = tile.ensure_system(
            "eco",
            {
                "producers": rng.uniform(300, 600),
                "herbivores": rng.uniform(40, 80),
                "carnivores": rng.uniform(5, 15),
            }
        )

        climate = tile.climate or "temperate"
        phase, season_name = GetSeason(climate, world_time)
        eco["season"] = season_name  # store for debug / description

        # --- Base modifiers from climate ---
        if climate == "tropical":
            growth_mod, mortality_mod = 1.2, 0.9
        elif climate == "polar":
            growth_mod, mortality_mod = 0.6, 1.3
        else:
            growth_mod, mortality_mod = 1.0, 1.0

        # --- Seasonal modulation (sinusoidal) ---
        # Temperate: four smooth peaks per year
        # Tropical: two strong wet/dry oscillations
        seasonal_amp = 0.25  # strength of season swing
        if climate == "temperate":
            season_factor = 1 + seasonal_amp * math.sin(phase * 4 * math.pi)
        elif climate == "tropical":
            season_factor = 1 + seasonal_amp * math.sin(phase * 2 * math.pi)
        else:  # polar
            season_factor = 1 + seasonal_amp * math.sin(phase * math.pi)

        # Apply season to growth (producers flourish in spring/wet season)
        prod = eco["producers"]
        herb = eco["herbivores"]
        carn = eco["carnivores"]
        K = 800.0

        d_producers = (0.05 * growth_mod * season_factor * prod * (1 - prod / K)
                       - 0.01 * herb * mortality_mod) * dt

        d_herbivores = (0.02 * prod * growth_mod * season_factor
                        - 0.03 * carn * mortality_mod
                        - 0.01 * herb * mortality_mod) * dt

        d_carnivores = (0.015 * herb * growth_mod
                        - 0.02 * carn * mortality_mod) * dt

        # Random environmental noise
        noise = lambda: rng.uniform(-0.02, 0.02)
        eco["producers"] = max(0.0, prod + d_producers + noise() * prod)
        eco["herbivores"] = max(0.0, herb + d_herbivores + noise() * herb)
        eco["carnivores"] = max(0.0, carn + d_carnivores + noise() * carn)

    # --- Optional: mild diffusion to neighboring tiles (migration) ---
    height = len(world)
    width = len(world[0])
    diffusion_rate = 0.03

    for y in range(height):
        for x in range(width):
            tile = world[y][x]
            eco = tile["eco"]
            neighbors = GetNeighbors(world, x, y)
            for neighbor in neighbors:
                n_eco = neighbor["eco"]
                for key in ["herbivores", "carnivores"]:
                    diff = diffusion_rate * (n_eco[key] - eco[key])
                    eco[key] += diff * dt

    return world

def SyncBiotaFromEco(tile):
    if "eco" not in tile or "biota" not in tile:
        return
    eco = tile["eco"]
    flora = tile["biota"]["flora"]
    fauna = tile["biota"]["fauna"]

    scale_f = eco["producers"] / max(1, sum(flora.values()))
    scale_h = eco["herbivores"] / max(1, sum(fauna.values()))

    for k in flora:
        flora[k] = max(0, int(flora[k] * scale_f))
    for k in fauna:
        fauna[k] = max(0, int(fauna[k] * scale_h))

def GetSeason(climate: str, world_time: int):
    """
    Return a normalized seasonal phase (0–1) and human-readable season name.
    Uses a simple sinusoidal cycle, different per climate zone.
    """
    # Different cycle speeds for different climates
    if climate == "tropical":
        seasons_per_year = 2  # wet/dry
    elif climate == "temperate":
        seasons_per_year = 4  # spring, summer, autumn, winter
    else:
        seasons_per_year = 1  # polar has one slow long cycle

    phase = (world_time % (365 // seasons_per_year)) / (365 // seasons_per_year)
    angle = 2 * math.pi * phase  # 0..2π per season

    # Map phase → descriptive label
    if climate == "temperate":
        season_names = ["spring", "summer", "autumn", "winter"]
    elif climate == "tropical":
        season_names = ["wet", "dry"]
    else:
        season_names = ["polar"]

    season_index = int(phase * len(season_names))
    season_name = season_names[season_index % len(season_names)]

    return phase, season_name

def CheckAndTriggerEcoEvents(world, macro, clock, region=None):
    from tile_events import TriggerEventFromLibrary
    for tile in GetActiveTiles(world, "eco"):
        eco = tile.get_system("eco")
        if not eco:
            continue

        producers = eco.get("producers", 0)
        herbivores = eco.get("herbivores", 0)
        carnivores = eco.get("carnivores", 0)

        # 🌿 Example trigger 1: bloom event
        if producers > 750 and not tile.has_tag("blooming"):
            TriggerEventFromLibrary(tile, "forest_bloom")

        # 🐍 Example trigger 2: predator surge event
        if carnivores / max(herbivores, 1) > 1.5:
            TriggerEventFromLibrary(tile, "predator_surge")

        # 🪲 Example trigger 3: collapse due to imbalance
        if herbivores < 5 and producers > 700:
            TriggerEventFromLibrary(tile, "ecological_collapse")

def PlotEcosystemHistory(history, sample_coords=(0,59)):
    plt.figure(figsize=(10,6))
    plt.plot(history["tick"], history["producers"], label=" Producers")
    plt.plot(history["tick"], history["herbivores"], label=" Herbivores")
    plt.plot(history["tick"], history["carnivores"], label=" Carnivores")
    plt.xlabel("Tick")
    plt.ylabel("Population")
    plt.title(f"Trophic-Level Dynamics at Tile {sample_coords}")
    plt.legend()
    plt.grid(True)
    plt.show()

def RunHistorySimulation(world, rng, steps=200, sample_coords=(0, 59)):
    x, y = sample_coords  # (x, y) order
    history = {"tick": [], "producers": [], "herbivores": [], "carnivores": []}

    for tick in range(steps):

        world = SimulateTrophicEcosystem(world, rng, tick)
        tile = world[y][x]
        eco = tile["eco"]
        history["tick"].append(tick)
        history["producers"].append(eco["producers"])
        history["herbivores"].append(eco["herbivores"])
        history["carnivores"].append(eco["carnivores"])

    return history