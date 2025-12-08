# directory economy.py/
from random import Random
from tile_state import TileState
from resource_catalog import GetResourcesForTerrain, GetResourcesForTile, GetResourceType
from world_utils import GetActiveTiles
from entities.settlement_factory import CreateSettlementAI
import math

REGION_TRAIT_BONUSES = {
    "mining": ["iron", "stone", "crystallized water"],
    "fortress": ["iron", "stone"],
    "fertile": ["root_tubers", "fungal_clusters"],
    "abundant_wood": ["timber", "golden timber"],
    "dense_fauna": ["meat"],
    "fishing": ["fish", "reeds"],
    "nomads": ["spices", "iron grass"],
    "trade_routes": ["spices", "salt"],
    "civilization": ["luxury_wood", "lucid_seed"]
}
REGION_MULTIPLIER_INIT = 1.25 # Initial boost at world creation
REGION_MULTIPLIER_TICK = 1.06 # Persistent tick boost

# --- Economy helpers
def GetSettlementCoordsByID(world, settlement_id):
    """
    Return (x, y) coordinates of a Settlement with a given ID.
    If not found, returns None.
    """
    for y, row in enumerate(world):
        for x, tile in enumerate(row):
            econ = tile.get_system("economy")
            if econ and econ.get("id") == settlement_id:
                return (x, y)
    return None

def GetSettlementByID(world, settlement_id):
    """
    Return (tile, economy) tuple for the specified Settlement ID.
    If not found, returns None.
    """

    for tile in GetActiveTiles(world, "economy"):
        econ = tile.get_system("economy")
        if econ and econ.get("id") == settlement_id:
            return (tile, econ)
    return None


def GetAllSettlementIDs(world):
    """
    Return a list of all Settlement IDs present in the world.
    """
    settlement_ids = []
    for tile in GetActiveTiles(world, "economy"):
        econ = tile.get_system("economy")
        if econ and "id" in econ:
            settlement_ids.append(econ["id"])
    return settlement_ids

# -----------------------------
# Settlement Category Helpers
# -----------------------------

def get_region_resource_tags(tile):
    """Derive resource tags from the tile's regional keys (from DetectRegions)."""
    # NOTE: This is a simplified derivation since the macro object is not available here.
    tags = set()
    for r_type in tile.regions.keys():
        r_type = r_type.replace("_cluster", "").replace("ocean_", "").replace("continent", "diverse")
        if r_type == "mountain": tags.add("mining")
        elif r_type == "forest": tags.add("abundant-wood")
        elif r_type == "dryland": tags.add("nomads")
        elif r_type == "lake" or r_type == "coastal": tags.add("fishing")
        elif r_type == "diverse": tags.add("civilization")
    return tags

def get_settlement_category(tile):
    """Return the category string or None."""
    econ = tile.get_system("economy")
    return econ.get("settlement_category") if econ else None


def set_settlement_category(tile, category: str):
    """Force-set the settlement category."""
    econ = tile.get_system("economy")
    if econ is not None:
        econ["settlement_category"] = category


def remove_settlement_category(tile):
    """Clear the settlement category field if it exists."""
    econ = tile.get_system("economy")
    if econ and "settlement_category" in econ:
        econ["settlement_category"] = None


def is_settlement_category(tile, category: str) -> bool:
    """Check if tile's settlement is of a given category."""
    econ = tile.get_system("economy")
    return econ and econ.get("settlement_category") == category

# -----------------------------
# Settlement Types Helpers
# -----------------------------

def get_settlement_types(tile) -> list:
    """Return list of types for this settlement."""
    econ = tile.get_system("economy")
    if econ is None:
        return []
    return econ.get("settlement_types", [])


def has_settlement_type(tile, type_name: str) -> bool:
    """Check if settlement has a type."""
    types = get_settlement_types(tile)
    return type_name in types


def add_settlement_type(tile, type_name: str):
    """Add a type to the list if not already present."""
    econ = tile.get_system("economy")
    if econ is None:
        return
    types = econ.setdefault("settlement_types", [])
    if type_name not in types:
        types.append(type_name)


def remove_settlement_type(tile, type_name: str):
    """Remove the type if it exists."""
    econ = tile.get_system("economy")
    if econ is None:
        return
    types = econ.setdefault("settlement_types", [])
    if type_name in types:
        types.remove(type_name)

def modify_settlement(tile, category=None, add_type=None, remove_type=None):
    """Convenient batch updater for settlements."""
    if category is not None:
        set_settlement_category(tile, category)

    if add_type:
        add_settlement_type(tile, add_type)

    if remove_type:
        remove_settlement_type(tile, remove_type)

def sigmoid_lite(x, threshold=1.0):
    return x / (abs(x) + threshold)

def logistic(x, midpoint=0, k=1.0):
    return 1.0 / (1.0 + math.exp(-k * (x - midpoint)))

def tanh_eq(x, scale=1.0):
    return math.tanh(x * scale)

def diminishing(x, power=0.5):
    return x ** power

def assign_settlement_category(tile):
    """
    Returns a high-level category string for a settlement.
    Considers climate, biome, and available tile resources.
    """
    resources = GetResourcesForTile(tile)
    biome = tile.biome or "unknown"
    climate = tile.climate or "temperate"
    tags = tile.tags or []

    # --- SPECIAL TAG RULES ---
    if "trade_hub" in tags:
        return "trade_post"
    if "military_path" in tags:
        return "fort"

    # --- CLIMATE / BIOME DRIVEN ---
    if climate in ("polar", "subpolar") or biome in ("tundra", "cold_steppe"):
        if "supplies_deficit" in tags or "hungry" in tags:
            return "camp"
        return "outpost"

    if biome in ("forest", "rainforest"):
        return "forest_village"

    if biome in ("mountain", "alpine"):
        if "iron" in resources or "metal_ore" in resources:
            return "mining_camp"
        return "mountain_hamlet"

    if biome in ("desert", "dry_steppe"):
        if "oasis" in tags:
            return "oasis_town"
        return "desert_settlement"

    # --- RESOURCE BASED ---
    if "grain" in resources or "livestock" in resources:
        return "farming_village"

    if "wood" in resources:
        return "logging_village"

    if "stone" in resources or "metal_ore" in resources:
        return "mining_village"

    # --- DEFAULT ---
    return "village"


def assign_settlement_types(tile):
    """
    Returns a list of traits describing the settlement.
    Considers climate, biome, and resource profile.
    """
    types = []
    resources = GetResourcesForTile(tile)
    biome = tile.biome or "unknown"
    climate = tile.climate or "temperate"
    tags = tile.tags or []

    # --- ECONOMIC SPECIALIZATION ---
    if "grain" in resources or "livestock" in resources:
        if climate not in ("polar", "subpolar"):
            types.append("agrarian")

    if "wood" in resources:
        types.append("logging")

    if "stone" in resources or "metal_ore" in resources:
        types.append("mining")

    if any(r in resources for r in ("spices", "silk", "luxury_wood", "incense")):
        types.append("luxury_goods")

    # --- TRADE ---
    if "trade_hub" in tags or climate == "temperate":
        # temperate climates usually produce surplus for trade
        types.append("trade_focused")

    if "river" in tags or "riverside" in tags:
        types.append("river_trade")

    if "coastal" in tags:
        types.append("maritime_trade")

    # --- MILITARY / STRATEGIC ---
    if "iron" in resources or "metal_ore" in resources:
        types.append("militaristic")

    if "border_conflict" in tags or biome in ("mountain", "tundra"):
        types.append("defensive")

    # --- INDUSTRY ---
    if "clay" in resources or "coal" in resources:
        types.append("industrial")

    # --- MONOPOLISTIC RESOURCE TYPE ---
    if len(resources) == 1:
        types.append("monopolistic")

    return types

def InitializeSettlementEconomy(world, rng: Random):
    for row in world:
        for tile in row:
            if not isinstance(tile, TileState): continue
            if tile.terrain != "settlement": continue

            origin_terrain = tile.origin_terrain or "plains"

            # Use per-tile resource detection (considers tags & origin terrain)
            base_resources = GetResourcesForTile(tile)  # <- FIX: pass tile, not a terrain name
            subs = {k: round(v * rng.uniform(0.5, 1.5), 2) for k, v in base_resources.items()}

            # --- NEW: Apply Regional Trait Bonuses to initial sub-commodities (Initialization) ---
            region_tags = get_region_resource_tags(tile)

            for trait in region_tags:
                resources_to_boost = REGION_TRAIT_BONUSES.get(trait, [])
                for r_name in resources_to_boost:
                    if r_name in subs:
                        # Give a strong initial bonus if the settlement is in a resource-rich region
                        subs[r_name] = round(subs[r_name] * rng.uniform(1.0, REGION_MULTIPLIER_INIT), 3)

            base_supplies = rng.uniform(80, 150)
            base_wealth = rng.uniform(50, 120)
            base_population = rng.uniform(80, 300)
            base_prosperity = base_supplies + base_wealth - base_population * 0.2

            econ = {
                "id": rng.randint(1, 9999),
                "settlement_category": assign_settlement_category(tile),
                "settlement_type": assign_settlement_types(tile),
                "name": f"Settlement_{tile.x}_{tile.y}",
                "population": base_population,
                "supplies": base_supplies,
                "prosperity": base_prosperity,
                "power_projection": base_prosperity * 0.1,
                "production": rng.uniform(6, 10),
                "consumption": rng.uniform(5, 8),
                "wealth": base_wealth,
                "price_multiplier": 1.0,
                "sub_commodities": subs,
                "origin_terrain": tile.origin_terrain or tile.terrain,
                "biome": tile.biome or "unknown"
            }

            tile.attach_system("economy", econ)
    return world

def InitializeAllRelationships(world):
    all_entities = []

    for row in world:
        for tile in row:
            if tile.entities:
                all_entities.extend(tile.entities)

    # Initialize
    for ent in all_entities:
        rel = ent.components.get("relationship")
        if rel:
            rel.initialize(ent, all_entities)

def AttachSettlementAgents(world):
    for row in world:
        for tile in row:
            econ = tile.get_system("economy")
            if econ:
                ent = CreateSettlementAI(tile)
                tile.entities.append(ent)


    # NOW initialize relationships
    InitializeAllRelationships(world)

def SimulateSettlementEconomy(world, rng=None):
    import random
    rng = rng or random.Random()

    BASE_PROD_PER_CAPITA = 0.08
    BASE_CONS_PER_CAPITA = 0.07


    for tile in GetActiveTiles(world, "economy"):
        econ = tile.get_system("economy")
        if not econ:
            continue

        # --- Weather influence -----------------------------------------
        weather = tile.get_system("weather")
        weather_mod = 1.0
        if weather:
            state = weather.get("state", "")
            if state == "rain":
                weather_mod = 1.1
            elif state == "storm":
                weather_mod = 0.9
            elif state == "drought":
                weather_mod = 0.6

        # --- Core production/consumption -------------------------------
        population = econ["population"]
        prod = population * BASE_PROD_PER_CAPITA
        prod *= logistic(weather_mod, midpoint=1.0, k=4.0)  # stable weather effect

        stress_factor = tanh_eq(1.0 - (econ["supplies"] / max(population, 1)), 1.5)
        cons = population * BASE_CONS_PER_CAPITA * (1.0 + 0.1 * stress_factor)

        delta = prod - cons

        econ["supplies"] = max(0.0, econ["supplies"] + sigmoid_lite(delta, 5.0))

        # --- Wealth change from surplus or deficit ---------------------
        econ["wealth"] += diminishing(max(delta, 0), power=0.7)
        econ["wealth"] = max(0.0, econ["wealth"])

        # --- Population responds to living conditions -----------------
        supply_ratio = econ["supplies"] / max(1.0, population)
        wealth_ratio = econ["wealth"] / 100.0

        growth_pressure = 0.5 * sigmoid_lite(supply_ratio - 1.0, 0.3) \
                          + 0.5 * sigmoid_lite(wealth_ratio - 0.5, 0.3)

        # logistic prevents chaotic spikes
        growth_rate = logistic(growth_pressure, midpoint=0.5, k=4.0)

        econ["population"] = int(max(10, population * growth_rate))

        # --- Sub-commodity fluctuations --------------------------------
        subs = econ.get("sub_commodities", {})
        for name, value in subs.items():
            drift = tanh_eq(delta * 0.002, 0.5)
            subs[name] = max(0.0, round(value + drift, 3))
        econ["sub_commodities"] = subs

        commodities_mod = ComputeSubCommoditiesModifier(tile)

        econ["wealth"] += commodities_mod

        pp_base = diminishing(econ["wealth"], 0.5) \
                  + diminishing(econ["population"], 0.5)

        pp = 0.7 * econ["power_projection"] + 0.3 * pp_base
        econ["power_projection"] = pp

        print ("SOME PP: ", econ["power_projection"])

        # econ["price_multiplier"] = ComputeSupplyDemandPrice(econ)
        econ["price_multiplier"] = econ["price_multiplier"] = 1.0 + sigmoid_lite((cons - prod), 10.0) * 0.5

        # --- Record tick history --------------------------------------
        # RecordEconomyHistory(econ)

    return world

def ComputeSubCommoditiesModifier(tile):
    """
    Broad category modifier: food/material/trade/luxury
    Safe diminishing wealth modifier to prevent runaway growth.
    """
    econ = tile.get_system("economy")  # <-- GET ECON FROM TILE
    types = econ.get("settlement_type", [])
    subs = econ.get("sub_commodities", {})

    # --- NEW: Apply Regional Trait Bonuses (Persistent Boost) ---
    region_tags = get_region_resource_tags(tile)
    for trait in region_tags:
        resources_to_boost = REGION_TRAIT_BONUSES.get(trait, [])
        for name in subs:
            if name in resources_to_boost:
                # Apply small persistent tick boost
                subs[name] *= REGION_MULTIPLIER_TICK

    if not types or not subs:
        return 0.0

    TYPE_TO_RESOURCE_TYPES = {
        "agrarian": ["food"],
        "logging": ["material"],
        "mining": ["material", "trade"],
        "luxury_goods": ["luxury", "trade"],
        "trade_focused": ["all"],
        "river_trade": ["food", "trade"],
        "maritime_trade": ["food", "trade"],
        "militaristic": ["material"],
        "defensive": [],
        "industrial": ["material"],
        "monopolistic": ["all"],
    }

    # gentle category boosts before wealth calc
    for stype in types:
        res_types = TYPE_TO_RESOURCE_TYPES.get(stype, [])

        if res_types == ["all"] and stype == "trade_focused":
            for name in subs:
                subs[name] *= 1.03  # gentler
            continue

        if res_types == ["all"] and stype == "monopolistic":
            # strong early, weaker later
            for name in subs:
                subs[name] *= 1.12
            continue

        for name in subs:
            category = GetResourceType(name)
            if category in res_types:
                subs[name] *= 1.06  # +6% gentle boost

    # round for stability
    for k in subs:
        subs[k] = round(subs[k], 3)

    econ["sub_commodities"] = subs

    # aggregate sub_commodity score
    total_strength = sum(subs.values())

    # wealth gain = diminishing returns
    wealth_gain = diminishing(total_strength, power=0.65)

    return round(wealth_gain, 3)

def ComputeSupplyDemandPrice(econ):
    """
    Returns a simple price multiplier based on:
      - demand = population * base need
      - supply = sum of all sub_commodities
    """

    population = econ.get("population", 100)
    subs = econ.get("sub_commodities", {})

    total_supply = sum(subs.values()) or 0.1

    # Base demand weight (adjustable)
    base_demand = population * 0.02

    # supply-demand ratio
    ratio = base_demand / max(total_supply, 1)

    # Convert ratio → price multiplier
    # ratio 1.0 → price = 1.0
    # ratio >1 → scarcity → price ↑
    # ratio <1 → plenty → price ↓
    price = 1.0 + (ratio - 1.0) * 0.5

    return max(0.5, min(price, 3.0))  # clamp



def RandomSettlementPerturbation(world, macro, clock, region=None):
    from random import choice
    import random

    # rng = random.Random(clock.global_tick * 100 + clock.local_tick)
    rng = clock.rng
    settlement_ids = GetAllSettlementIDs(world)

    # Pick a few random settlements to perturb this tick
    for vid in rng.sample(settlement_ids, min(3, len(settlement_ids))):
        tile, econ = GetSettlementByID(world, vid)
        agent = SettlementEconomyAgent(tile)

        # Randomly fluctuate economy a bit
        if rng.random() < 0.5:
            agent.add_supplies(-1, 3)
        if rng.random() < 0.5:
            agent.add_wealth(-1, 2)
        if rng.random() < 0.3:
            # Affect a random commodity
            if econ["sub_commodities"]:
                cname = choice(list(econ["sub_commodities"].keys()))
                agent.add_sub_commodity(0.5, cname)

        # print(f"[Tick {clock.global_tick}:{clock.local_tick:02d}] Perturbed {econ['name']} → {agent.summary()}")

def RecordEconomyHistory(econ: dict, max_length: int = 30):
    """
    Append per-tick history of supplies, wealth, and sub_commodities.
    Keeps only the last `max_length` entries.
    """
    history = econ.setdefault("history", {
        "supplies": [],
        "wealth": [],
        "sub_commodities": {}
    })

    # Record main stats
    history["supplies"].append(econ["supplies"])
    history["wealth"].append(econ["wealth"])

    # Record sub-commodities
    for name, value in econ.get("sub_commodities", {}).items():
        history["sub_commodities"].setdefault(name, []).append(value)
        # Trim sub-commodity list
        if len(history["sub_commodities"][name]) > max_length:
            del history["sub_commodities"][name][0]

    # Trim core lists
    if len(history["supplies"]) > max_length:
        del history["supplies"][0]
    if len(history["wealth"]) > max_length:
        del history["wealth"][0]

    econ["history"] = history

import random

class SettlementEconomyAgent:
    """
    Wrapper class for manipulating a single Settlement's economy data easily.
    Provides simple random incremental changes to supplies, wealth, and sub-commodities.
    """

    def __init__(self, tile):
        econ = tile.get_system("economy")
        if not econ:
            raise ValueError(f"Tile at ({tile.x}, {tile.y}) is not a Settlement or has no economy system.")
        self.tile = tile
        self.econ = econ
        self.rng = random.Random(econ["id"])

    # --- Core Adjusters ----------------------------------------------------

    def add_supplies(self, min_amount: float, max_amount: float):
        delta = self.rng.uniform(min_amount, max_amount)
        self.econ["supplies"] = max(0, self.econ["supplies"] + delta)
        return self.econ["supplies"]

    def add_wealth(self, min_amount: float, max_amount: float):
        delta = self.rng.uniform(min_amount, max_amount)
        self.econ["wealth"] = max(0, self.econ["wealth"] + delta)
        return self.econ["wealth"]

    def add_sub_commodity(self, min_amount: float, commodity_name: str):
        subs = self.econ.setdefault("sub_commodities", {})
        current_value = subs.get(commodity_name, 0.0)
        # delta = self.rng.uniform(-abs(min_amount), abs(min_amount))
        # subs[commodity_name] = max(0.0, round(current_value + delta, 3))
        subs[commodity_name] = current_value + min_amount;
        self.econ["sub_commodities"] = subs
        return subs[commodity_name]

    # --- Optional Helpers --------------------------------------------------

    def summary(self):
        """Return a small snapshot of this Settlement economy."""
        return {
            "id": self.econ["id"],
            "name": self.econ["name"],
            "supplies": round(self.econ["supplies"], 2),
            "wealth": round(self.econ["wealth"], 2),
            "sub_commodities": dict(self.econ["sub_commodities"]),
        }
