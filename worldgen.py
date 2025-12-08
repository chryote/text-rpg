# directory worldgen.py

import random
import sys
import math
import json
import curses
from tile_state import TileState

from math import sqrt
from noise import pnoise2, pnoise3
from resource_catalog import GetResourcesForTerrain, GetResourcesForTile

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

# --- CLIMATE HUMIDITY BASELINES ------------------------------------------
CLIMATE_HUMIDITY_BASELINE = {
    "tropical": 0.8,   # humid, frequent rain
    "temperate": 0.5,  # balanced
    "polar": 0.3,      # dry air, low moisture
    "arid": 0.15,      # deserts or drylands (optional)
}

TERRAIN_HUMIDITY_MODIFIER = {
    "dryland": 0.6,    # semi-arid
    "oasis": 1.1,      # locally humid
    "desert": 0.3,     # arid
    "mountain": 0.8,   # condensation zones
    "wetlands": 1.2,   # very humid
    "coastal": 1.1,    # sea moisture
}

# --- World helpers

def GetTile(world, x, y):
    """Safely get a tile by coordinates (x, y).
    Note: internally, world is indexed as world[y][x].
    """
    height = len(world)
    width = len(world[0]) if height > 0 else 0
    if 0 <= y < height and 0 <= x < width:
        return world[y][x]
    return None

def GetNeighbors(world, x, y):
    height = len(world)
    width = len(world[0])
    neighbors = []
    for ny in range(max(0, y - 1), min(height, y + 2)):
        for nx in range(max(0, x - 1), min(width, x + 2)):
            if nx == x and ny == y:
                continue
            neighbors.append(world[ny][nx])
    return neighbors

def GetNeighborsRadius(world, x, y, radius=2):
    """
    Return all tiles within Chebyshev distance `radius` (square neighborhood). Does not include center.
    """
    height = len(world)
    width = len(world[0])
    neighbors = []
    for ny in range(max(0, y - radius), min(height, y + radius + 1)):
        for nx in range(max(0, x - radius), min(width, x + radius + 1)):
            if nx == x and ny == y:
                continue
            neighbors.append(world[ny][nx])
    return neighbors

def GetRegionByTile(macro, x, y, region_type=None):
    """
    Return the region info that contains tile (x, y) in O(1) time using lookup.
    """
    if not macro or "lookup" not in macro or "regions" not in macro:
        return None

    entry = macro["lookup"].get((x, y))
    if not entry:
        return None
    if region_type and entry["region_type"] != region_type:
        return None

    rid = entry["region_id"]
    for region in macro["regions"]:
        if region["id"] == rid and region["terrain"] == entry["region_type"]:
            return region
    return None


def GetRegionByID(macro, region_id, region_type=None):
    """
    Find and return a region by its numeric ID.
    Optionally restrict to a specific region_type (e.g. 'continent', 'forest_cluster').
    Returns None if not found.
    """
    if not macro or "regions" not in macro:
        return None

    for region in macro["regions"]:
        if region["id"] == region_id:
            if region_type and region["terrain"] != region_type:
                continue
            return region
    return None

def AssignRegionNames(macro, seed=42):
    """
    Assign names to all regions in macro["regions"].
    """
    if not macro or "regions" not in macro:
        return macro

    rng = random.Random(seed)
    for region in macro["regions"]:
        region["name"] = GenerateRegionName(region, rng)

    return macro

def AssignRegionTraits(macro, world, rng=None):
    """
    Assign narrative and gameplay traits to each region based on terrain,
    biome distribution, and climate richness.
    Adds 'region_traits' dict with:
      - 'category': main qualitative tags
      - 'description': human-readable flavor text
      - 'flavor_tags': hooks for AI/world narrative
    """
    if rng is None:
        rng = random.Random(999)

    for region in macro.get("regions", []):
        terrain = region["terrain"]
        climates = region.get("climate_distribution")
        dominant_climate = max(climates, key=climates.get) if climates else "temperate"

        traits = []
        flavor_tags = []

        # --- Basic climate & terrain identity ---
        if dominant_climate == "tropical":
            traits.append("lush")
            flavor_tags.append("dense_fauna")
        elif dominant_climate == "polar":
            traits.append("frozen")
            flavor_tags.append("scarce_resources")
        elif dominant_climate == "temperate":
            traits.append("mild")
            flavor_tags.append("fertile")

        if terrain == "mountain_cluster":
            traits.append("resource-rich")
            flavor_tags += ["mining", "fortress"]
        elif terrain == "forest_cluster":
            traits.append("abundant_wood")
            flavor_tags += ["herbalism", "bandits"]
        elif terrain == "dryland_cluster":
            traits.append("harsh")
            flavor_tags += ["nomads", "ancient_ruins"]
        elif terrain == "lake_cluster":
            traits.append("tranquil")
            flavor_tags += ["fishing", "trade_routes"]
        elif terrain == "ocean_cluster":
            traits.append("vast")
            flavor_tags += ["storms", "sea_monsters"]
        elif terrain == "continent":
            traits.append("diverse")
            flavor_tags += ["civilization", "trade_routes"]

        # --- Random narrative hook ---
        narrative_hooks = [
            "ancient ruins", "mystical springs", "abandoned fortress",
            "bandit territory", "spiritual pilgrimage site", "meteor crater",
            "forgotten empire", "haunted forest"
        ]
        if rng.random() < 0.35:
            hook = rng.choice(narrative_hooks)
            traits.append("ancient")
            flavor_tags.append(hook.replace(" ", "_"))

        # --- Generate description ---
        desc = f"A {', '.join(traits)} region ({terrain}), known for {', '.join(flavor_tags[:3])}."

        region["region_traits"] = {
            "category": traits,
            "description": desc,
            "flavor_tags": flavor_tags
        }

    return macro


# --- Generation functions (deterministic via rng)

def GenerateWorld(rng, width=100, height=100, num_continents=3, scale=20.0):
    """
    Generate base world using Perlin noise as a reference point to spawn a tile.

    rng: an instance of random.Random for deterministic randomness
    """
    # Use a seed offset for noise functions that is deterministic from rng
    seed_offset = rng.randint(0, 100000)

    # Step 1: Pick random continent centers (deterministic via rng)
    continents = [
        (rng.randint(0, width - 1), rng.randint(0, height - 1), rng.uniform(0.3, 0.6))
        for _ in range(num_continents)
    ]
    # tuple: (cx, cy, radius_factor)

    world = []
    for y in range(height):
        row = []
        for x in range(width):

            # Step 2: Base perlin variation
            nx = x / scale
            ny = y / scale
            noise_val = pnoise2(nx + seed_offset, ny + seed_offset, octaves=3)

            # Step 3: Find nearest continent center and apply falloff
            distances = []
            for cx, cy, rf in continents:
                dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                influence = max(0.0, 1.0 - (dist / (width * rf)))  # radius falloff
                distances.append(influence)
            continent_influence = max(distances) if distances else 0.0  # strongest nearby landmass

            # Step 4: Combine noise + influence to get elevation
            elevation = (noise_val * 0.5) + (continent_influence * 1.0) - 0.3

            # Step 5: Assign biome by elevation
            if elevation > 0.7:
                tile_type = "mountain"
                movement_method = ["all"]
                movement_cost = 4
            elif elevation > 0.6:
                tile_type = "riverside"
                movement_method = ["all"]
                movement_cost = 3
            elif elevation > 0.4:
                tile_type = "forest"
                movement_method = ["all"]
                movement_cost = 2
            elif elevation > 0.1:
                tile_type = "plains"
                movement_method = ["all"]
                movement_cost = 1
            else:
                tile_type = "deep_water"
                movement_method = ["boat"]
                movement_cost = 4

            tile = TileState(
                x=x,
                y=y,
                layer="world",
                elevation=round(elevation, 3),
                terrain=tile_type,
                climate=None,  # assigned later
                biome=None,
                origin_terrain = tile_type,
                movement_method = movement_method,
                movement_cost = movement_cost,
                tags=[],
                systems={
                    "meta": {
                        "seed_offset": seed_offset,
                        "continent_influence": round(continent_influence, 3),
                        "noise": round(noise_val, 3)
                    }
                }
            )
            row.append(tile)
        world.append(row)

    world = ClassifySpecialTiles(world)
    return world

def ClassifySpecialTiles(world):
    height = len(world)
    width = len(world[0]) if height > 0 else 0

    for y in range(height):
        for x in range(width):
            tile = world[y][x]
            neighbors = GetNeighbors(world, x, y)

            # Mark coastlines — land next to deep water
            if tile.terrain in ["plains", "forest", "mountain"]:
                if any(n.terrain == "deep_water" for n in neighbors):
                    tile.movement_method = ["all"]
                    tile.movement_cost = 1
                    tile.set_terrain("coastal")

            # Mark wetlands — riverside next to forest or plains but not mountain
            elif tile.terrain == "riverside":
                if any(n.terrain in ["forest", "plains"] for n in neighbors):
                    tile.movement_method = ["all"]
                    tile.movement_cost = 2
                    tile.set_terrain("wetlands")

            # Tag ocean tiles explicitly
            elif tile.terrain == "deep_water":
                tile.add_tag("ocean")

    return world


def AssignClimate(world, rng, noise_scale=15.0):
    """
    Assign climate to each tile and use uneven latitude border.
    rng: deterministic random generator (used to pick the noise offset)
    """
    seed = rng.randint(0, 100000)
    height = len(world)
    width = len(world[0]) if height > 0 else 0

    for y, row in enumerate(world):
        lat = y / (height - 1) if height > 1 else 0
        for x, tile in enumerate(row):
            nx, ny = x / noise_scale, y / noise_scale
            variation = pnoise2(nx + seed, ny + seed, octaves=2)
            lat_mod = lat + variation * 0.05 # Add small distortion

            if lat_mod < 0.2 or lat_mod > 0.8:
                climate = 'polar'
                seasons = 1
            elif 0.2 <= lat_mod < 0.4 or 0.6 < lat_mod <= 0.8:
                climate = 'temperate'
                seasons = 4
            else:
                climate = "tropical"
                seasons = 2

            tile.climate = climate
            tile.seasons = seasons

            # --- New humidity system baseline ---
            base_humidity = CLIMATE_HUMIDITY_BASELINE.get(climate, 0.5)

            # Modify baseline by terrain / biome later if available
            if tile.terrain in ["dryland", "oasis"]:
                base_humidity *= 0.7
            elif tile.terrain in ["wetlands", "coastal"]:
                base_humidity *= 1.2

            # Clamp 0..1 and attach
            tile.attach_system("humidity", {
                "base": round(max(0.0, min(1.0, base_humidity)), 3),
                "current": round(base_humidity, 3),
            })

    return world

# --- Climate maps: temperature + rainfall ---------------------------------
def ComputeTemperatureAndRainfall(world, rng,
                                  equator_temp=28.0,     # °C at equator baseline
                                  pole_temp=-12.0,       # °C at pole baseline
                                  noise_scale=20.0,
                                  temp_noise_amp=3.0,
                                  lapse_rate=12.0,       # °C per normalized elevation (0..1) -> steep for game scale
                                  seasonal_temp_amp=6.0,
                                  base_rainfall_by_climate=None):
    """
    Compute smooth per-tile temperature and rainfall values:
      - temperature: function of latitude, elevation (lapse), Perlin noise, and season offset (tile.seasons)
      - rainfall: function of humidity baseline, wind advection, and orographic uplift (windward mountains)
    Stores results into:
        tile.attach_system('climate_map', {'temperature': float, 'rainfall': float})
        and convenience properties tile.temperature, tile.rainfall (in systems as well)
    RNG is deterministic Random instance.
    """

    try:
        from noise import pnoise2, pnoise3
    except Exception:
        # If noise unavailable, fallback to tiny random jitter
        pnoise2 = lambda x, y, octaves=1: 0.0
        pnoise3 = lambda x, y, z, octaves=1: 0.0

    if base_rainfall_by_climate is None:
        base_rainfall_by_climate = {
            "tropical": 6.0,
            "temperate": 3.0,
            "polar": 1.0,
            "arid": 0.6
        }

    height = len(world)
    width = len(world[0]) if height > 0 else 0

    seed_offset = rng.randint(0, 100000)
    # Precompute a small seasonal_phase from existing tile.seasons (if available) to add latitude-seasonal bias
    for y, row in enumerate(world):
        lat = y / (height - 1) if height > 1 else 0.5  # 0..1 (0 = top / north)
        # map to -1..1 where 0 is equator at lat=0.5
        lat_from_equator = 1.0 - abs(lat - 0.5) * 2.0

        for x, tile in enumerate(row):
            nx = x / noise_scale
            ny = y / noise_scale

            # --- Temperature ---
            # Base lat interpolation
            # equator_temp at lat==0.5, pole_temp at lat==0 or lat==1
            lat_frac = abs(lat - 0.5) * 2.0  # 0 at equator, 1 at poles
            base_temp = equator_temp * (1.0 - lat_frac) + pole_temp * lat_frac

            # Add Perlin noise small-scale variation
            noise_val = pnoise2(nx + seed_offset * 0.01, ny + seed_offset * 0.01, octaves=3)
            noise_val = noise_val * temp_noise_amp  # -amp..+amp

            # Elevation cooling (lapse rate scaled to tile.elevation which is approx -1..1 in your generator; but we store 0..1)
            elev = max(0.0, min(1.0, float(tile.elevation if tile.elevation is not None else 0.0)))
            elev_cooling = lapse_rate * elev

            # Seasonal bias if tile.seasons is present (gives more swing in temperate)
            season_phase = 0.0
            if hasattr(tile, "seasons") and getattr(tile, "seasons", None):
                # small deterministic extra modulation via tile.systems season if present
                ssys = tile.get_system("season")
                if ssys and "phase" in ssys:
                    season_phase = float(ssys["phase"])
            # Convert to seasonal temp offset (sinusoidal around phase)
            season_offset = seasonal_temp_amp * (math.sin(2 * math.pi * season_phase) if season_phase else 0.0)

            temperature = base_temp + noise_val - elev_cooling + season_offset

            # --- Rainfall ---
            # Start from climate baseline and humidity system
            climate_key = (tile.climate or "temperate")
            base_rain = base_rainfall_by_climate.get(climate_key, 3.0)

            # Humidity system (if present) strongly influences rainfall
            hum_sys = tile.get_system("humidity") or {}
            hum = max(0.0, min(1.0, float(hum_sys.get("current", hum_sys.get("base", 0.5)))))

            # Wind/orographic uplift: if tile is on windward side of elevation relative to wind vector, add more rain
            wind = tile.get_system("wind") or {}
            orographic = 0.0
            if wind and "vector" in wind:
                # check upwind tile moisture difference
                dx, dy = wind.get("vector", (0.0, 0.0))
                # convert to nearest neighbor indices
                ux = int(round(x - dx))
                uy = int(round(y - dy))
                if 0 <= ux < width and 0 <= uy < height:
                    upwind_tile = world[uy][ux]
                    upwind_h = upwind_tile.get_system("humidity", {}).get("current", hum)
                    # if upwind is wetter and current tile is higher elevation, uplift occurs
                    up_elev = upwind_tile.elevation if hasattr(upwind_tile, "elevation") else 0.0
                    if elev > up_elev:
                        orographic = (elev - up_elev) * (upwind_h) * 4.0  # multiplier tuned for game scale

            # Perlin noise for rainfall streaks
            rain_noise = (pnoise2((nx + 50.0) + seed_offset * 0.02, (ny + 50.0) - seed_offset * 0.02, octaves=2) + 1.0) / 2.0

            # Combine into rainfall mm/day-ish units (game scale)
            rainfall = max(0.0, base_rain * (0.4 + 1.6 * hum) + orographic * 2.0 + rain_noise * 1.5)

            # Normalize / clamp into a 0..10 game-friendly scale and attach
            temp_val = round(float(temperature), 2)
            rain_val = round(float(rainfall), 3)

            climate_map = tile.ensure_system("climate_map", {})
            climate_map.update({
                "temperature": temp_val,
                "rainfall": rain_val,
                "lat_equator_factor": round(lat_from_equator, 3)
            })
            tile.attach_system("climate_map", climate_map)

            # convenience top-level friendly properties in systems
            tile.attach_system("temperature", {"value": temp_val})
            tile.attach_system("rainfall", {"value": rain_val})

            # also set short-cuts for legacy code convenience
            try:
                tile.temperature = temp_val
                tile.rainfall = rain_val
            except Exception:
                # not critical if tile object doesn't accept new attributes in your environment
                pass

    return world

def ComputeSoilAndResources(world, rng):
    """
    Derive soil fertility and multiple resource richness values for each tile.
    Attaches:
        tile.attach_system("soil", {"fertility": float})
        tile.attach_system("resources", {"iron": 0.5, "timber": 0.7, ...})
    """

    for row in world:
        for tile in row:
            biome = tile.biome or "unknown"
            elev = float(tile.elevation)
            rain = tile.get_system("rainfall").get("value", 3.0)
            terrain = tile.terrain
            climate = tile.climate or "temperate"

            # --- Soil Fertility ------------------------------------------
            base_fertility = 0.5
            if biome in ["rainforest", "wetland", "savanna"]:
                base_fertility = 0.8
            elif biome in ["grassland", "forest"]:
                base_fertility = 0.7
            elif biome in ["semi_arid", "scrubland", "steppe"]:
                base_fertility = 0.4
            elif biome in ["desert", "glacier", "permafrost"]:
                base_fertility = 0.1

            rain_factor = min(1.0, rain / 5.0)
            elev_factor = 1.0 - max(0.0, elev - 0.5)
            fertility = base_fertility * 0.5 + 0.5 * rain_factor * elev_factor
            fertility = round(max(0.0, min(1.0, fertility + rng.uniform(-0.05, 0.05))), 3)

            tile.attach_system("soil", {"fertility": fertility})

            # --- Multi-Resource Richness ---------------------------------
            # dynamic resource allocation (terrain + tag aware)
            resources = GetResourcesForTile(tile)
            for r in list(resources.keys()):
                # scale by fertility & randomness
                resources[r] = round(resources[r] * (0.5 + fertility) * rng.uniform(0.8, 1.2), 3)

            # slight scaling by fertility (richer soil → better natural goods)
            for rname in list(resources.keys()):
                if rname in ["grain", "timber", "herbs"]:
                    resources[rname] = round(resources[rname] * (0.5 + fertility), 3)

            tile.attach_system("resources", resources)

    return world


# --- Smooth biome derivation using continuous temp + rainfall -------------
def DeriveBiomeFromClimate(world,
                            temp_thresholds=None,
                            rain_thresholds=None):
    """
    Fully climate-aware biome assignment.
    Covers all biomes used across worldgen + ecosystem + economy:
      glacier, tundra, permafrost, alpine,
      forest, grassland, wetland,
      montane_forest, rainforest, savanna, mangrove,
      desert, scrubland, steppe, cold_steppe, semi_arid, semi_savanna
    """

    if temp_thresholds is None:
        # °C approximate bands for world-scale simulation
        temp_thresholds = [-999, -10, 0, 10, 20, 30, 999]
    if rain_thresholds is None:
        # Rainfall intensity bands (game-scale arbitrary units)
        rain_thresholds = [0.0, 0.6, 1.5, 3.0, 6.0, 10.0, 9999.0]

    # 6x6 mapping grid (temp × rainfall)
    # Each row = temperature band, from coldest → hottest
    # Each col = rainfall band, from driest → wettest
    mapping = [
        #   0:arid   1:semi   2:moderate  3:humid   4:wet   5:rainforest
        ["glacier", "permafrost", "tundra", "tundra", "alpine", "alpine"],          # <- very cold
        ["cold_steppe", "tundra", "tundra", "boreal_forest", "montane_forest", "montane_forest"],  # cold
        ["steppe", "grassland", "forest", "wetland", "montane_forest", "rainforest"],  # cool/mild
        ["scrubland", "grassland", "forest", "forest", "rainforest", "rainforest"],   # temperate/warm
        ["desert", "semi_arid", "savanna", "savanna", "rainforest", "mangrove"],      # hot
        ["desert", "semi_arid", "savanna", "savanna", "rainforest", "mangrove"],      # very hot
    ]

    biome_tags = [
        'glacier', 'tundra', 'permafrost', 'alpine', 'boreal_forest',
        'forest', 'grassland', 'wetland',
        'montane_forest', 'rainforest', 'savanna', 'mangrove',
        'scrubland', 'steppe', 'cold_steppe', 'semi_arid', 'semi_savanna', 'desert'
    ]

    def find_band(val, thresholds):
        for i in range(len(thresholds) - 1):
            if thresholds[i] <= val < thresholds[i + 1]:
                return i
        return len(thresholds) - 2

    for y, row in enumerate(world):
        for x, tile in enumerate(row):
            cm = tile.get_system("climate_map") or {}
            temp = cm.get("temperature", tile.get_system("temperature").get("value", 12.0))
            rain = cm.get("rainfall", tile.get_system("rainfall").get("value", 3.0))
            elev = float(tile.elevation if tile.elevation is not None else 0.0)
            terr = getattr(tile, "terrain", None)

            t_band = find_band(temp, temp_thresholds)
            r_band = find_band(rain, rain_thresholds)
            biome = mapping[t_band][r_band]

            # --- Adjustments for realism ---
            if elev > 0.8:
                if temp < 0:
                    biome = "glacier"
                elif temp < 10:
                    biome = "alpine"
                else:
                    biome = "montane_forest"

            # Extremely dry regions
            if rain < 0.5:
                biome = "desert" if temp > 10 else "cold_steppe"

            # Transition zones (semi)
            if 0.5 <= rain < 1.5 and biome in ["grassland", "savanna"]:
                biome = "semi_arid" if temp > 15 else "steppe"

            # Humid tropics
            if temp > 20 and rain > 5:
                biome = "rainforest"

            # Wet low-elevation near water
            if terr in ["coastal", "riverbank"] and rain > 4:
                biome = "mangrove"

            if tile.has_tag("lake") or terr == "wetlands":
                biome = "wetland"

            # Clean up and assign
            existing = tile.tags if isinstance(tile.tags, list) else []
            existing = [t for t in existing if t not in biome_tags]
            existing.append(biome)
            tile.tags = existing
            tile.biome = biome

    return world


def DetectRegions(world):
    """
    Detect and label large contiguous regions of similar terrain type:
    - Continents / islands (land)
    - Oceans
    - Lakes
    - Forest clusters
    - Dryland clusters
    - Mountain clusters

    Returns:
        (world, macro): tuple
          world: the modified 2D list of tiles with region IDs attached
          macro: a dictionary with all aggregated region data and lookup map
    """
    height = len(world)
    width = len(world[0]) if height > 0 else 0
    visited_global = set()
    regions = []
    lookup = {}
    region_id_counter = 0

    # --- Helper to flood-fill any condition ---
    def flood_fill(x, y, condition):
        stack = [(x, y)]
        cluster = []
        visited_local = set()

        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in visited_local or (cx, cy) in visited_global:
                continue
            if not (0 <= cx < width and 0 <= cy < height):
                continue
            tile = world[cy][cx]
            if not condition(tile):
                continue

            visited_local.add((cx, cy))
            visited_global.add((cx, cy))
            cluster.append((cx, cy))

            for n in GetNeighbors(world, cx, cy):
                stack.append((n.x, n.y))

        return cluster

    # --- Condition functions ---
    def is_land(tile):
        return tile.terrain not in ["deep_water"]

    def is_ocean(tile):
        return "ocean" in tile.tags

    def is_lake(tile):
        return "lake" in tile.tags

    def is_forest(tile):
        tags = tile.tags
        return tile.terrain == "forest" or any(t in tags for t in ["forest", "rainforest", "montane_forest"])

    def is_dry(tile):
        tags = tile.tags
        return tile.terrain == "dryland" or "desert" in tags

    def is_mountain(tile):
        tags = tile.tags
        return tile.terrain == "mountain" or "alpine" in tags

    # --- Flood fill by category ---
    def detect_generic(label, condition):
        nonlocal region_id_counter
        for y in range(height):
            for x in range(width):
                if (x, y) in visited_global:
                    continue
                tile = world[y][x]
                if not condition(tile):
                    continue

                cluster = flood_fill(x, y, condition)
                if not cluster:
                    continue

                region_id_counter += 1
                region_id = region_id_counter
                # Compute summary stats
                elevations = [world[cy][cx].elevation for (cx, cy) in cluster]
                climates = [world[cy][cx].climate for (cx, cy) in cluster]
                minx, maxx = min(c[0] for c in cluster), max(c[0] for c in cluster)
                miny, maxy = min(c[1] for c in cluster), max(c[1] for c in cluster)

                climate_counts = {}
                for c in climates:
                    climate_counts[c] = climate_counts.get(c, 0) + 1
                total = sum(climate_counts.values()) or 1
                climate_dist = {k: round(v / total, 3) for k, v in climate_counts.items()}

                region_info = {
                    "id": region_id,
                    "terrain": label,
                    "tiles": cluster,
                    "area": len(cluster),
                    "avg_elevation": round(sum(elevations) / len(elevations), 3),
                    "climate_distribution": climate_dist,
                    "bounds": {"minx": minx, "maxx": maxx, "miny": miny, "maxy": maxy},
                    "name": None
                }
                regions.append(region_info)

                # Tag each tile + build lookup
                for (cx, cy) in cluster:
                    tile = world[cy][cx]
                    if tile.regions is None:
                        tile.regions = {}
                    tile.regions[label] = region_id
                    lookup[(cx, cy)] = {"region_type": label, "region_id": region_id}

    # --- Run all categories ---
    visited_global.clear()
    detect_generic("continent", is_land)

    visited_global.clear()
    detect_generic("ocean_cluster", is_ocean)

    visited_global.clear()
    detect_generic("lake_cluster", is_lake)

    visited_global.clear()
    detect_generic("forest_cluster", is_forest)

    visited_global.clear()
    detect_generic("dryland_cluster", is_dry)

    visited_global.clear()
    detect_generic("mountain_cluster", is_mountain)

    # --- Return both layers ---
    macro = {"regions": regions, "lookup": lookup}
    return world, macro

def MarkRegionLocalDirection(world, macro):
    """
    For each tile inside a region, calculate its relative (x,y) position
    from that region's center, normalized to [-1, 1].

    Adds:
        tile["region_offset"][region_type] = {
            "dx": ...,
            "dy": ...,
            "region_id": ...
        }
        tile["region_direction"][region_type] = {
            "dir": "north"/"southwest"/etc,
            "region_id": ...
        }
    """
    if not macro or "regions" not in macro:
        return world

    for region in macro["regions"]:
        tiles = region["tiles"]
        if not tiles:
            continue

        # Bounding box and centroid
        minx, maxx = region["bounds"]["minx"], region["bounds"]["maxx"]
        miny, maxy = region["bounds"]["miny"], region["bounds"]["maxy"]
        cx = (minx + maxx) / 2
        cy = (miny + maxy) / 2

        span_x = max(1, maxx - minx)
        span_y = max(1, maxy - miny)

        for (x, y) in tiles:
            dx = ((x - cx) / (span_x / 2))
            dy = ((y - cy) / (span_y / 2))
            dx = max(-1, min(1, dx))
            dy = max(-1, min(1, dy))

            # Compass direction
            horiz, vert = "", ""
            if dy < -0.33:
                vert = "north"
            elif dy > 0.33:
                vert = "south"

            if dx < -0.33:
                horiz = "west"
            elif dx > 0.33:
                horiz = "east"

            if not horiz and not vert:
                direction = "center"
            elif horiz and vert:
                direction = vert + horiz  # e.g. 'southwest'
            else:
                direction = horiz or vert

            # Store per-tile info
            tile = world[y][x]
            region_type = region["terrain"]
            region_id = region["id"]

            if not isinstance(tile.region_offset, dict):
                tile.region_offset = {}
            if not isinstance(tile.region_direction, dict):
                tile.region_direction = {}

            tile.region_offset[region_type] = {
                "dx": round(dx, 3),
                "dy": round(dy, 3),
                "region_id": region_id
            }

            tile.region_direction[region_type] = {
                "dir": direction,
                "region_id": region_id
            }

    return world

def GetRegionSectorTiles(world, macro, region_type, region_id, sector_name):
    """
    Return list of tiles (or coordinates) within a region
    that belong to a given directional sector.

    Args:
        world: 2D world grid
        macro: macro structure from DetectRegions()
        region_type: e.g. "continent", "mountain_cluster"
        region_id: numeric region ID
        sector_name: e.g. "north", "southwest", "center"

    Returns:
        list of (x, y) coordinates belonging to that sector
    """
    region = None
    # 1. Find region
    for r in macro["regions"]:
        if r["id"] == region_id and r["terrain"] == region_type:
            region = r
            break
    if not region:
        return []

    result_tiles = []

    # 2. Iterate through region's tiles
    for (x, y) in region["tiles"]:
        tile = world[y][x]
        dirs = tile.get("region_direction", {}).get(region_type)
        if not dirs:
            continue

        # new version stores {'dir': 'northwest', 'region_id': N}
        direction = dirs["dir"] if isinstance(dirs, dict) else dirs

        if direction == sector_name:
            result_tiles.append((x, y))

    return result_tiles

def GenerateRegionName(region, rng=None):
    """
    Generate a procedural name for a region based on its type, climate, and biome.
    """
    if rng is None:
        rng = random.Random(region["id"])

    climate_bias = next(iter(sorted(region["climate_distribution"], key=lambda k: region["climate_distribution"][k], reverse=True)), "temperate")

    # --- Word sets ---
    color_by_climate = {
        "polar": ["Frost", "Ice", "Pale", "Glacier", "White", "Crystal"],
        "temperate": ["Green", "Amber", "Silver", "Autumn", "Verdant", "Golden"],
        "tropical": ["Emerald", "Crimson", "Azure", "Sun", "Rain", "Amber"],
        "desert": ["Ashen", "Sable", "Burning", "Dust", "Ivory", "Dune"]
    }

    tone = color_by_climate.get(climate_bias, ["Grey", "Silent", "Hidden"])

    roots = [
        "Aurel", "Varn", "Karesh", "Morn", "Drav", "Eld", "Theren", "Sable",
        "Zeth", "Myrr", "Lun", "Cind", "Tir", "Ardan", "Vel", "Karn", "Silv",
        "Nor", "Mar", "Osth"
    ]
    suffixes = ["ia", "ar", "en", "or", "eth", "an", "oth", "ir", "el", "os", "uin", "al"]

    # --- Generator logic ---
    t = region["terrain"]

    if t == "continent":
        base = rng.choice(roots) + rng.choice(suffixes)
        title = rng.choice(["", "Lands", "Empire", "Dominion", "Realm", "Reach", "Haven"])
        return (f"{base}" if not title else f"{base} {title}").strip()

    elif t == "forest_cluster":
        adj = rng.choice(tone + ["Elder", "Whispering", "Verdant", "Deep"])
        noun = rng.choice(["Woods", "Grove", "Forest", "Veil", "Thicket"])
        suffix = rng.choice(suffixes)
        return f"{adj} {noun}{suffix}"

    elif t == "mountain_cluster":
        prefix = rng.choice(tone + ["Iron", "High", "Storm", "Frost"])
        noun = rng.choice(["Peaks", "Range", "Mounts", "Spine", "Crest"])
        suffix = rng.choice(suffixes)
        return f"{prefix} {noun}{suffix}"

    elif t == "dryland_cluster":
        prefix = rng.choice(tone + ["Burning", "Howling", "Dust"])
        noun = rng.choice(["Expanse", "Wastes", "Dunes", "Sands", "Flats"])
        suffix = rng.choice(suffixes)
        return f"{prefix} {noun}{suffix}"

    elif t == "lake_cluster":
        noun = rng.choice(["Lake", "Mere", "Pond", "Basin", "Cradle"])
        suffix = rng.choice(tone + roots)
        return f"{noun} {suffix}"

    elif t == "ocean_cluster":
        prefix = rng.choice(tone + ["Tempest", "Silent", "Moonlit"])
        noun = rng.choice(["Sea", "Ocean", "Reach", "Depths"])
        return f"The {prefix} {noun}"

    else:
        base = rng.choice(roots) + rng.choice(suffixes)
        return base

def UpdateWeather(world, world_time, rng=None,
                      smooth_factor=0.8,
                      humidity_diffusion=0.05):
    """
    New optimized weather simulation:
    - Precomputed Perlin noise
    - 3 compact passes (weather → wind → humidity)
    - No nested neighbor loops
    - In-place system updates
    """

    import math
    from worldsim import GetSeason
    import world_index_store

    weather_noise = world_index_store.weather_noise
    wind_noise = world_index_store.wind_noise
    rain_noise = world_index_store.rain_noise

    H = len(world)
    W = len(world[0])

    # Precompute season for climate groups
    clim_cache = {}
    def season_phase(climate):
        if climate not in clim_cache:
            clim_cache[climate] = GetSeason(climate, world_time)
        return clim_cache[climate]

    # ------------------------------------------------------------
    # PASS 1 — WEATHER state (single loop)
    # ------------------------------------------------------------
    for y in range(H):
        wy = weather_noise[y]
        for x in range(W):
            tile = world[y][x]
            climate = tile.climate

            # --- Weather intensity (no more perlin) ---
            base, var = (0.6, 0.4) if climate == "tropical" else \
                        (0.5, 0.3) if climate == "temperate" else \
                        (0.4, 0.2)

            raw = (wy[x] + 1) * 0.5      # normalize to 0..1
            new_intensity = base + (raw - 0.5) * (2 * var)
            new_intensity = max(0.0, min(1.0, new_intensity))

            # Smooth with previous
            wsys = tile.ensure_system("weather")
            prev_intensity = wsys.get("intensity", new_intensity)
            intensity = prev_intensity * smooth_factor + new_intensity * (1 - smooth_factor)
            intensity = max(0, min(1, intensity))

            # --- State / tag ---
            old_state = wsys.get("state", "clear_weather")

            if intensity > 0.85:
                state = "storm"
            elif intensity > 0.6:
                state = "rain"
            elif intensity < 0.25 and tile.terrain in ["plains", "forest", "mountain", "wetlands"]:
                state = "drought"
            else:
                state = "clear_weather"

            # --- Update system ---
            wsys["intensity"] = round(intensity, 3)
            wsys["state"] = state

            # --- Update tile tags (fast replace) ---
            tgs = tile.tags
            if old_state in tgs:
                tgs.remove(old_state)
            if state not in tgs:
                tgs.append(state)

            # --- Season ---
            phase, name = season_phase(climate)
            tile.ensure_system("season").update({
                "phase": round(phase, 3),
                "name": name
            })

    # ------------------------------------------------------------
    # PASS 2 — WIND field (single loop)
    # ------------------------------------------------------------
    dirs = ["wind_direction_moving_north","wind_direction_moving_northeast","wind_direction_moving_east","wind_direction_moving_southeast",
            "wind_direction_moving_south","wind_direction_moving_southwest","wind_direction_moving_west","wind_direction_moving_northwest"]

    for y in range(H):
        wn_row = wind_noise[y]
        for x in range(W):
            tile = world[y][x]

            # angle 0..2π
            ang = (wn_row[x] + 1) * math.pi

            dx = math.cos(ang)
            dy = math.sin(ang)

            # direction index
            idx = int(((math.atan2(dy, dx) + math.pi) / (2 * math.pi)) * 8) % 8
            tag = dirs[idx]

            wsys = tile.ensure_system("wind")
            wsys["vector"] = (round(dx, 3), round(dy, 3))
            wsys["direction"] = tag

            # Add tag if missing
            if tag not in tile.tags:
                tile.tags.append(tag)

    # ------------------------------------------------------------
    # PASS 3 — HUMIDITY diffusion (buffer-based, no neighbor scans)
    # ------------------------------------------------------------
    newH = [[0]*W for _ in range(H)]

    for y in range(H):
        rr = rain_noise[y]
        for x in range(W):
            tile = world[y][x]
            hsys = tile.ensure_system("humidity")
            h = hsys.get("current", hsys.get("base", 0.5))

            state = tile.get_system("weather")["state"]

            # weather → humidity
            if state == "rain":   h += 0.03
            elif state == "storm": h += 0.07
            elif state == "drought": h -= 0.06

            # seasonal effect
            phase,_ = season_phase(tile.climate)
            h += math.sin(phase * 2*math.pi) * 0.01

            # water bodies add moisture
            if tile.has_any_tag("ocean","lake","river","wetlands"):
                h += 0.02

            # wind advection (1 fast check instead of 8 neighbors)
            wind = tile.get_system("wind")
            dx, dy = wind["vector"]
            ux = x - int(round(dx))
            uy = y - int(round(dy))
            if 0 <= ux < W and 0 <= uy < H:
                up = world[uy][ux].get_system("humidity")["current"]
                h += humidity_diffusion * (up - h)

            newH[y][x] = max(0, min(1, h))

    # Final writeback
    for y in range(H):
        for x in range(W):
            hsys = world[y][x].get_system("humidity")
            hsys["current"] = round(newH[y][x], 3)

    return world


# --- Detect and Tag Inland Lakes ---
def DetectAndTagLakes(world):
    """
    Detects clusters of inland deep_water tiles (lakes) and updates the surrounding terrain.
    """
    height = len(world)
    width = len(world[0]) if height > 0 else 0
    visited = set()

    def flood_fill(x, y):
        cluster = []
        stack = [(x, y)]

        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in visited:
                continue
            visited.add((cx, cy))

            tile = world[cy][cx]
            if tile.terrain != "deep_water":
                continue

            cluster.append((cx, cy))

            for n in GetNeighbors(world, cx, cy):
                nx, ny = n.x, n.y
                if (nx, ny) not in visited and n.terrain == "deep_water":
                    stack.append((nx, ny))

        return cluster

    # Scan all deep_water tiles to find clusters
    for y in range(height):
        for x in range(width):
            if (x, y) in visited:
                continue
            tile = world[y][x]
            if tile.terrain != "deep_water":
                continue

            cluster = flood_fill(x, y)
            if not cluster:
                continue

            # Check if cluster touches world edge (then it's an ocean)
            touches_edge = any(
                cx == 0 or cy == 0 or cx == width - 1 or cy == height - 1 for cx, cy in cluster
            )

            if not touches_edge:
                # Inland cluster → lake
                for (cx, cy) in cluster:
                    lake_tile = world[cy][cx]
                    if not lake_tile.has_tag("lake"):
                        lake_tile.remove_tag("ocean")
                        lake_tile.add_tag("lake")

                    # Update nearby coastals to wetlands
                    for neighbor in GetNeighbors(world, cx, cy):
                        # neighbor is a tile dict; modify it directly
                        if neighbor.terrain == "coastal":
                            neighbor.movement_method = ["all"]
                            neighbor.movement_cost = 1
                            # call the proper setter so index updates occur
                            try:
                                neighbor.set_terrain("wetlands")
                            except Exception:
                                neighbor.terrain = "wetlands"

                            if not neighbor.has_tag('lake_edge'):
                                neighbor.add_tag('lake_edge')

    return world

def TagRivers(world, macro, max_rivers=20, branch_chance=0.15, seed=12345):
    """
    Simulate and tag river paths from mountainous/riverside tiles
    toward coastal or deep_water areas.
    Adds 'river' to tile['tags'] and 'has_river': True flag.

    Args:
        world: 2D world grid
        macro: macro regions (for locating mountain regions)
        max_rivers: how many rivers to spawn
        branch_chance: probability to split a flow mid-path
    """
    rng = random.Random(seed)
    height = len(world)
    width = len(world[0]) if height > 0 else 0

    def is_valid(x, y):
        return 0 <= x < width and 0 <= y < height

    def is_water(tile):
        return tile.terrain in ["coastal", "deep_water", "lake"]

    # --- Find river sources ---
    potential_sources = []
    for y in range(height):
        for x in range(width):
            tile = world[y][x]
            t = tile.terrain
            if t in ["mountain", "riverside"]:
                potential_sources.append((x, y))

    rng.shuffle(potential_sources)
    sources = potential_sources[:max_rivers]

    # --- Utility: pick lowest neighbor ---
    def lowest_neighbor(x, y):
        neighbors = GetNeighbors(world, x, y)
        if not neighbors:
            return None
        lowest = min(neighbors, key=lambda n: n.elevation)
        if lowest.elevation < world[y][x].elevation:
            return (lowest.x, lowest.y)
        return None

    # --- Main flow simulation ---
    river_count = 0
    for (sx, sy) in sources:
        cx, cy = sx, sy
        path = [(cx, cy)]
        for _ in range(200):  # max river length
            next_tile = lowest_neighbor(cx, cy)
            if not next_tile:
                break
            nx, ny = next_tile
            tile = world[ny][nx]

            if is_water(tile) or "lake" in tile.tags:
                # river reach coast or lake
                path.append((nx, ny))
                break

            # Mark river
            if tile.tags is None:
                tile.tags = []
            if "river" not in tile.tags:
                tile.remove_tag("river")
                tile.add_tag("river")
            meta = tile.ensure_system("meta")
            meta["has_river"] = True

            path.append((nx, ny))

            # Random branch (optional small tributary)
            if rng.random() < branch_chance and len(path) > 5:
                bx, by = cx, cy
                if (bx + 1 < width) and (by + 1 < height):
                    alt_next = lowest_neighbor(bx + rng.choice([-1, 0, 1]), by + rng.choice([-1, 0, 1]))
                    if alt_next:
                        ax, ay = alt_next
                        if not is_water(world[ay][ax]):
                            world[ay][ax].remove_tag("river")
                            world[ay][ax].add_tag("river")
                            meta = world[ay][ax].ensure_system("meta")
                            meta["has_river"] = True

            cx, cy = nx, ny

        river_count += 1

    print(f"Tagged {river_count} rivers across world.")
    return world

def PlaceSettlements(world, rng, min_distance=3, base_chance=0.1, density_scale=20.0):
    """
    Place settlements procedurally using Perlin noise as a density mask.
    rng: deterministic random generator
    """
    height = len(world)
    width = len(world[0]) if height > 0 else 0
    settlements = []

    # --- Generate Perlin noise for population density ---
    # Use a deterministic noise offset from rng
    density_seed = rng.randint(0, 100000)
    for y in range(height):
        for x in range(width):
            nx = x / density_scale
            ny = y / density_scale
            density = pnoise2(nx + density_seed * 0.7, ny + density_seed * 0.7, octaves=2)
            # normalize to 0..1
            density = (density + 1) / 2

            tile = world[y][x]
            tile.density_from_settlement_generation = round(density, 2)

    # --- Place settlements based on combined noise and distance ---
    coords = [(x, y) for y in range(height) for x in range(width)]
    rng.shuffle(coords)  # deterministic shuffle

    for x, y in coords:
        tile = world[y][x]

        # Only consider good base terrain
        if tile.terrain in ['oasis', 'deep_water', 'mountain']:
            continue

        # Use density noise to influence chance
        local_chance = base_chance * (tile.density_from_settlement_generation * 2.0)  # scale higher density = more likely

        if rng.random() > local_chance:
            continue

        # Enforce min spacing
        too_close = any(abs(vx - x) + abs(vy - y) < min_distance for vx, vy in settlements)
        if too_close:
            continue

        tile.set_terrain("settlement")
        # print ("SETTLEMENT : ", tile.terrain)
        if not tile.has_tag ('settlement'):
            tile.remove_tag('settlement')
            tile.add_tag('settlement')
        settlements.append((x, y))

    return world

def AddDrylands(world, rng, num_dryspots = 3, min_radius = 2, max_radius = 4):
    """
    Adds small clusters of dryland tiles after base world generation.
    """
    height = len(world)
    width = len(world[0]) if height > 0 else 0

    for _ in range(num_dryspots):
        # Pick a random center
        cx = rng.randint(0, width - 1)
        cy = rng.randint(0, height - 1)
        radius = rng.randint(min_radius, max_radius)

        # Apply a circular region with some noise to avoid perfect shapes
        for y in range(max(0, cy - radius), min(height, cy + radius + 1)):
            for x in range(max(0, cx - radius), min(width, cx + radius + 1)):
                dx, dy = x - cx, y - cy
                dist = sqrt(dx*dx + dy*dy)

                # add slight randomness to shape
                if dist < radius + rng.uniform(-0.8, 0.8):
                    tile = world[y][x]
                    # Only replace certain tile types (skip ocean, mountain)
                    if tile.terrain in ["plains", "forest"] and tile.climate == "tropical":
                        tile.movement_method = ["all"]
                        tile.movement_cost = 1
                        tile.set_terrain("dryland")

    return world

def RefineDrylandBiomes(world, rng):
    """
    Reclassify 'dryland' tiles into transitional biomes based on climate, humidity, and neighbors.
    """
    height = len(world)
    width = len(world[0]) if height > 0 else 0

    for y in range(height):
        for x in range(width):
            tile = world[y][x]
            if tile.terrain != "dryland":
                continue

            # Check climate and surrounding context
            neighbors = GetNeighbors(world, x, y)
            wet_neighbors = sum(1 for n in neighbors if n.terrain in ["wetlands", "oasis", "coastal"])
            humid_neighbors = sum(1 for n in neighbors if "rain" in n.tags or "wetland" in n.tags)

            # Default biome
            biome_tag = "semi_arid"

            # Slightly wetter drylands → steppe / savanna edge
            if tile.climate == "tropical" and humid_neighbors > 2:
                biome_tag = "semi_savanna"
            elif tile.climate == "temperate" and humid_neighbors > 1:
                biome_tag = "steppe"
            elif tile.climate == "polar":
                biome_tag = "cold_steppe"
            elif wet_neighbors == 0 and tile.climate == "tropical":
                biome_tag = "scrubland"
            elif wet_neighbors == 0 and tile.climate == "temperate":
                biome_tag = "barren_steppe"

            # Replace any previous biome tag
            biome_tags = [
                'glacier', 'tundra', 'permafrost', 'alpine', 'boreal_forest',
                'forest', 'grassland', 'wetland',
                'montane_forest', 'rainforest', 'savanna', 'mangrove',
                'scrubland', 'steppe', 'cold_steppe', 'semi_arid', 'semi_savanna', 'desert'
            ]
            tile.tags = [t for t in tile.tags if t not in biome_tags]
            tile.tags.append(biome_tag)
            tile.biome = biome_tag

    return world

def AddOases(world, rng, chance_per_tile = 0.05, max_cluster = 2, require_full_surround=True, radius_check=1, min_neighbors=3, exclude_near_settlement=True):
    """
    Adds small oases inside drylands with improved neighbor checks.
    """
    height = len(world)
    width = len(world[0]) if height > 0 else 0

    def neighbors_within_radius(x, y, r):
        return GetNeighborsRadius(world, x, y, radius=r)

    def is_suitable_start(x, y):
        tile = world[y][x]
        if tile.terrain != "dryland":
            return False

        # Avoid spawning next to settlements or invalid terrain
        if exclude_near_settlement:
            for n in neighbors_within_radius(x, y, 1):
                if n.terrain == "settlement":
                    return False

        # Gather neighbors in radius and ensure enough neighbors exist (not on extreme edges)
        neigh = neighbors_within_radius(x, y, radius_check)
        if len(neigh) < min_neighbors:
            return False

        dry_count = sum(1 for n in neigh if n.terrain == "dryland")

        if require_full_surround:
            return dry_count == len(neigh)
        else:
            # require at least 80% of neighbors to be dryland by default
            return (dry_count / len(neigh)) >= 0.8

    # We'll iterate in randomized order so clusters don't overlap due to scan order bias
    coords = [(x, y) for y in range(height) for x in range(width)]
    rng.shuffle(coords)

    for x, y in coords:
        if not is_suitable_start(x, y):
            continue

        if rng.random() >= chance_per_tile:
            continue

        cluster_radius = rng.randint(1, max_cluster)

        # Grow cluster but only onto dryland
        for dy in range(-cluster_radius, cluster_radius + 1):
            for dx in range(-cluster_radius, cluster_radius + 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    dist = sqrt(dx * dx + dy * dy)
                    if dist <= cluster_radius and rng.random() > 0.2:
                        neighbor = world[ny][nx]
                        # worldgen.py (inside AddOases) — replace block that set neighbor.terrain = "oasis"
                        if neighbor.terrain == "dryland":
                            # extra safety: do not overwrite settlements or special tiles
                            if neighbor.terrain != "settlement":
                                # Use the TileState API to mutate terrain so world index & hooks are updated
                                try:
                                    neighbor.set_terrain("oasis")
                                except Exception:
                                    # Fallback if set_terrain unavailable (defensive)
                                    neighbor.terrain = "oasis"
                                neighbor.origin_terrain = "oasis"
                                neighbor.movement_method = ["all"]
                                neighbor.movement_cost = 1

    return world

def BuildNoiseGrid(width, height, seed, scale, octaves):
    import noise
    return [
        [
            noise.pnoise3(
                (x + seed) / scale,
                (y + seed) / scale,
                seed / 100.0,
                octaves=octaves
            )
            for x in range(width)
        ]
        for y in range(height)
    ]
