# directory ecosystem.py/
from typing import Dict
from random import Random
from tile_state import TileState
from world_utils import GetActiveTiles

# --- MASTER SPECIES DEFINITIONS (unchanged) -------------------------------
flora_species = {"grass", "acacia", "tree", "fern", "moss", "reed", "lotus", "cactus", "shrub"}
herbivore_species = {"antelope", "elephant", "reindeer", "frog", "fish", "bird"}
carnivore_species = {"lion", "wolf", "snake", "scorpion", "crane", "lizard"}
omnivore_species = {"monkey"}

flora_tag = "flora"
fauna_tag = "fauna"

SPECIES = {
    s: {"terrain": flora_tag, "trophic": "producer"} for s in flora_species
} | {
    s: {"terrain": fauna_tag, "trophic": "herbivore"} for s in herbivore_species
} | {
    s: {"terrain": fauna_tag, "trophic": "carnivore"} for s in carnivore_species
} | {
    s: {"terrain": fauna_tag, "trophic": "omnivore"} for s in omnivore_species
}

# --- Utilities ------------------------------------------------------------
def is_flora(species: str) -> bool: return species in flora_species
def is_fauna(species: str) -> bool: return species in herbivore_species | carnivore_species | omnivore_species
def get_trophic(species: str) -> str: return SPECIES.get(species, {}).get("trophic", "unknown")

# --- Flora and Fauna Seeding ---------------------------------------------
def SeedFloraFauna(world, rng: Random):
    biome_flora = {
        "rainforest": {"tree": 0.7, "fern": 0.9, "moss": 0.6},
        "forest": {"tree": 0.7, "fern": 0.9, "moss": 0.6},
        "savanna": {"grass": 1.0, "acacia": 0.5},
        "tundra": {"moss": 0.5},
        "permafrost": {"moss": 0.5, "shrub": 0.5},
        "desert": {"cactus": 0.4, "shrub": 0.3},
        "scrubland": {"cactus": 0.4, "shrub": 0.3},
        "wetland": {"reed": 0.8, "lotus": 0.4},
    }
    biome_fauna = {
        "rainforest": {"monkey": 0.05, "snake": 0.03, "bird": 0.1},
        "forest": {"monkey": 0.05, "snake": 0.03, "bird": 0.1},
        "savanna": {"antelope": 0.08, "elephant": 0.02, "lion": 0.008},
        "tundra": {"reindeer": 0.06, "wolf": 0.01},
        "permafrost": {"reindeer": 0.05, "wolf": 0.04},
        "desert": {"lizard": 0.06, "scorpion": 0.02},
        "scrubland": {"lizard": 0.06, "scorpion": 0.02},
        "wetland": {"frog": 0.07, "fish": 0.1, "crane": 0.03},
    }

    for row in world:
        for tile in row:
            if not isinstance(tile, TileState):
                continue
            biome = next((tag for tag in tile.tags if tag in biome_flora), None)
            flora = biome_flora.get(biome, {})
            fauna = biome_fauna.get(biome, {})
            tile.attach_system("biota", {
                "flora": {k: v * rng.uniform(0.8, 1.2) for k, v in flora.items()},
                "fauna": {k: v * rng.uniform(0.8, 1.2) for k, v in fauna.items()},
            })
    return world

def ConvertBiotaToCounts(world, scale_factor_flora=300, scale_factor_fauna=100):
    for tile in GetActiveTiles(world, "biota"):
        if not isinstance(tile, TileState): continue
        biota = tile.get_system("biota")
        if not biota: continue
        flora_counts = {k: int(v * scale_factor_flora) for k, v in biota["flora"].items()}
        fauna_counts = {k: int(v * scale_factor_fauna) for k, v in biota["fauna"].items()}
        tile.attach_system("biota", {"flora": flora_counts, "fauna": fauna_counts})
    return world

def InitializeEcosystemFromBiota(world, rng: Random):
    for row in world:
        for tile in row:
            if not isinstance(tile, TileState): continue
            biota = tile.get_system("biota") or {}
            flora = biota.get("flora", {})
            fauna = biota.get("fauna", {})
            producers_sum = sum(v for k, v in flora.items() if k in flora_species)
            herb_sum = sum(v for k, v in fauna.items() if k in herbivore_species)
            carn_sum = sum(v for k, v in fauna.items() if k in carnivore_species)
            omni_sum = sum(v for k, v in fauna.items() if k in omnivore_species)
            herb_sum += omni_sum * 0.5
            carn_sum += omni_sum * 0.5
            tile.attach_system("eco", {
                "producers": producers_sum * rng.uniform(0.8, 1.2),
                "herbivores": herb_sum * rng.uniform(0.8, 1.2),
                "carnivores": carn_sum * rng.uniform(0.8, 1.2),
            })
    return world

def SimulateEco(world, rng=None, world_time=0, dt=1.0):
    """
    Unified ecosystem simulation.
    Replaces SimulateTrophicEcosystem() and SimulateBiotaEcosystem().

    Improvements:
    - Stable trophic oscillations (reduced random chaos)
    - Seasonal effects incorporated cleanly
    - Humidity, climate, soil fertility integrated
    - Produces explicit eco_risk tag per tile (used by trade route risk)
    """

    import math
    import random
    from worldsim import GetSeason
    from worldgen import GetNeighbors

    if isinstance(rng, int):
        rng = random.Random(rng)
    elif rng is None:
        rng = random.Random(world_time)

    height = len(world)
    width = len(world[0])

    for tile in GetActiveTiles(world, "eco"):
        eco = tile.ensure_system("eco", {"producers": 300, "herbivores": 60, "carnivores": 10})
        biota = tile.get_system("biota") or {}
        weather = tile.get_system("weather") or {}
        humidity = tile.get_system("humidity") or {"current": 0.5}
        soil = tile.get_system("soil") or {"fertility": 0.5}

        climate = tile.climate or "temperate"

        # Seasonal + climate adjustment
        phase, season_name = GetSeason(climate, world_time)
        eco["season"] = season_name
        seasonal_amp = 0.25

        if climate == "temperate":
            season_factor = 1 + seasonal_amp * math.sin(phase * 4 * math.pi)
        elif climate == "tropical":
            season_factor = 1 + seasonal_amp * math.sin(phase * 2 * math.pi)
        else:
            season_factor = 1 + seasonal_amp * math.sin(phase * math.pi)

        # Climate growth/mortality baseline
        if climate == "tropical":
            growth_mod = 1.2
            mortality_mod = 0.9
        elif climate == "polar":
            growth_mod = 0.6
            mortality_mod = 1.3
        else:
            growth_mod = 1.0
            mortality_mod = 1.0

        # Weather influence
        w_state = weather.get("state", "")
        if w_state == "rain":
            growth_mod *= 1.15
            mortality_mod *= 0.9
        elif w_state == "storm":
            growth_mod *= 0.85
            mortality_mod *= 1.2
        elif w_state == "drought":
            growth_mod *= 0.6
            mortality_mod *= 1.3

        # Humidity & soil fertility impact
        hum = humidity.get("current", 0.5)
        fert = soil.get("fertility", 0.5)

        growth_mod *= (0.7 + hum * 0.3)
        growth_mod *= (0.6 + fert * 0.4)

        # Trophic calculations
        prod = eco["producers"]
        herb = eco["herbivores"]
        carn = eco["carnivores"]
        K = 800.0

        d_producers = (
            (0.05 * growth_mod * season_factor * prod * (1 - prod / K))
            - 0.01 * herb * mortality_mod
        ) * dt

        d_herbivores = (
            (0.02 * prod * growth_mod * season_factor)
            - 0.03 * carn * mortality_mod
            - 0.008 * herb * mortality_mod
        ) * dt

        d_carnivores = (
            (0.015 * herb * growth_mod)
            - (0.02 * carn * mortality_mod)
        ) * dt

        # Controlled noise (reduced chaos)
        def eco_noise(scale=0.015):
            return rng.uniform(-scale, scale)

        eco["producers"] = max(0.0, prod + d_producers + eco_noise() * prod)
        eco["herbivores"] = max(0.0, herb + d_herbivores + eco_noise() * herb)
        eco["carnivores"] = max(0.0, carn + d_carnivores + eco_noise() * carn)

        # Sync back to biota counts
        flora = biota.get("flora", {})
        fauna = biota.get("fauna", {})

        if flora:
            total_flora = sum(flora.values()) or 1
            scale_f = eco["producers"] / total_flora
            for k in flora:
                flora[k] = int(flora[k] * scale_f)

        if fauna:
            total_fauna = sum(fauna.values()) or 1
            scale_h = eco["herbivores"] / total_fauna
            for k in fauna:
                fauna[k] = int(fauna[k] * scale_h)

        tile.attach_system("biota", {"flora": flora, "fauna": fauna})
        tile.attach_system("eco", eco)

        # Eco-risk descriptor → used by trade route risk
        carn_r = eco["carnivores"] / max(eco["herbivores"], 1)
        prod_r = eco["producers"] / max(K, 1)

        risk_score = (
            0.5 * carn_r +
            0.3 * (1 - prod_r) +
            (0.2 if w_state == "storm" else 0)
        )

        tile.attach_system("eco_risk", {"value": round(risk_score, 3)})

    return world

