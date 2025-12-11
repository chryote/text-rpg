# directory world_utils.py
import sys

from tile_state import TileState
from worldgen import GetNeighborsRadius
from math import sqrt
from resource_catalog import GetResourcesForTile

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

def ConvertWorldToTileState(world):
    """Convert 2D list of tile dicts into TileState objects."""
    return [
        [
            TileState(
                x=tile.get("x"),
                y=tile.get("y"),
                elevation=tile.get("elevation", 0.0),
                terrain=tile.get("terrain", "unknown"),
                climate=tile.get("climate"),
                biome=tile.get("biome"),
                tags=tile.get("tags", []),
                regions=tile.get("regions", {}),
                systems={
                    k: v for k, v in tile.items()
                    if k in ("eco", "economy", "biota", "weather")
                },
            )
            for tile in row
        ]
        for row in world
    ]


def SpreadTag(world, x, y, tag: str, radius: int = 1, chance: float = 1.0, include_center: bool = False):
    """
    Spread a tag outward from a tile (x, y) within the given radius.
    ...
    """
    import random
    count = 0
    height = len(world)
    width = len(world[0]) if height > 0 else 0

    if not (0 <= x < width and 0 <= y < height):
        return 0

    tiles_to_tag = GetNeighborsRadius(world, x, y, radius)
    if include_center:
        tiles_to_tag.append(world[y][x])

    for t in tiles_to_tag:
        if random.random() <= chance:
            if not t.has_tag(tag):
                t.add_tag(tag)
                count += 1

    return count


def GetActiveTiles(world, system_name):
    """
    Return list of tiles that have a specific system (e.g., economy).

    Behavior:
      - If a global WorldIndex is available via world_index_store.world_index,
        use that index (fast).
      - Otherwise fall back to scanning the whole world (backwards-compatible).

    This keeps all callers unchanged while giving instant speed benefits
    when the index is initialized and exposed in world_index_store.world_index.
    """
    # Lazy import to avoid circular import problems at module import time.
    try:
        # world_index_store should be a tiny module with `world_index = None`
        # main.py should set world_index_store.world_index = world_index after building it.
        import world_index_store
        widx = getattr(world_index_store, "world_index", None)
        if widx:
            # return a copy to avoid callers mutating internal index lists
            return list(widx.with_system(system_name))
    except Exception:
        # If anything goes wrong (module missing, import error, etc), fall through to scan
        pass

    # Backward-compatible full-scan fallback
    return [t for row in world for t in row if t.get_system(system_name)]

def GetTilesWithinRadius(world, x, y, radius=3, include_center=False):
    """
    Return tiles within Chebyshev distance `radius` (square neighborhood).
    Keeps bounds checks. Returns list[TileState].
    """
    height = len(world)
    width = len(world[0]) if height > 0 else 0
    result = []
    for ny in range(max(0, y - radius), min(height, y + radius + 1)):
        for nx in range(max(0, x - radius), min(width, x + radius + 1)):
            if nx == x and ny == y and not include_center:
                continue
            result.append(world[ny][nx])
    return result

def GetNearestTileWithSystem(world, x, y, system_name, max_radius=20):
    """
    Returns the nearest tile (TileState) that has a given system (e.g., 'economy'),
    searching by increasing radius (Manhattan/Chebyshev). Returns None if not found.
    """
    # try world_index fast-path if available
    try:
        import world_index_store
        widx = getattr(world_index_store, "world_index", None)
        if widx:
            candidates = widx.with_system(system_name)
            if not candidates:
                return None
            # simple nearest by Euclidean distance
            best = min(candidates, key=lambda t: (t.x - x) ** 2 + (t.y - y) ** 2)
            return best
    except Exception:
        pass

    # fallback: scan in expanding radius
    for r in range(max_radius + 1):
        tiles = GetTilesWithinRadius(world, x, y, radius=r, include_center=(r==0))
        if tiles:
            for t in tiles:
                if t.get_system(system_name):
                    return t
    return None

def RecalculateTileResources(tile):
    """
    Recompute resources for a specific tile using resource_catalog.GetResourcesForTile
    and attach as 'resources' system. Useful after terrain/biome changes.
    """
    try:
        resources = GetResourcesForTile(tile)
        tile.attach_system("resources", resources)
    except Exception:
        # defensive: do nothing if tile or module missing
        pass

def RecalculateWorldResources(world):
    """Re-run GetResourcesForTile on the entire world (cheap-ish)."""
    for row in world:
        for tile in row:
            RecalculateTileResources(tile)

def SaveWorldStateToMeta(world, macro):
    tile = world[0][0]
    meta = tile.get_system("meta")

    if meta is None:
        return  # world not initialized properly

    meta["world_state"] = macro.debug_state()

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


def _get_entity_info(entity):
    """Helper to extract standardized name and position string from an entity or tile."""
    if not entity:
        return {"name": "Unknown", "pos": "(N/A)"}

    # Check if it's an entity object (has get() for components)
    if hasattr(entity, 'get'):
        # Attempt to get the settlement name or fall back to entity ID/type
        name = entity.get("economy", {}).get("name") if entity.get("economy") else entity.id
    else:
        # Assume it's a TileState if it doesn't have .get
        if entity.entities:
            first_entity = entity.entities[0]
            # The Entity class stores the ID directly as an attribute (.id)
            name = first_entity.id
        else:
            name = getattr(entity, 'terrain', 'Tile')

    # Safely get coordinates
    if hasattr(entity, 'tile') and entity.tile:
        pos = f"({entity.tile.x},{entity.tile.y})"
    elif hasattr(entity, 'x') and hasattr(entity, 'y'):
        pos = f"({entity.x},{entity.y})"
    else:
        pos = "(N/A)"

    return {"name": name, "pos": pos}


def LogEntityEvent(entity, event_type: str, message: str, target_entity=None):
    """
    Standardized logging function for entity-driven events, handling optional target entities.
    Output format: [EVENT_TYPE] Source Name (x,y) [-> Target Name (x,y)]: Message
    """
    source_info = _get_entity_info(entity)

    # Start with the basic source log
    log_parts = [f"[{event_type.upper()}]", f"{source_info['name']} {source_info['pos']}"]

    # Add target information if provided
    if target_entity:
        target_info = _get_entity_info(target_entity)
        log_parts.append(f"-> {target_info['name']} {target_info['pos']}")

    log_parts.append(f": {message}")

    print(" ".join(log_parts))