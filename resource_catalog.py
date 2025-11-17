# directory resource_catalog.py
"""
Unified resource catalog for economy, AI, and world systems.
Defines resource types, trade classes, and metadata.
"""
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

RESOURCE_CATEGORIES = ["material", "food", "trade", "luxury", "cultural"]

RESOURCE_CATALOG = {
    # --- Food resources ----------------------------------------------------

    "root_tubers": {
        "type": "food",
        "terrain_bias": ['plains'],
        "tag_bias": [],
        "rarity": "common",
        "base_value": 1.0,
        "weight": 1.0,
        "desc": "Hardy underground tubers found across many climates."
    },
    "fungal_clusters": {
        "type": "food",
        "terrain_bias": ['plains', 'mountain', 'riverside', 'wetlands', 'dryland', 'forest', 'mountain', 'oasis'],
        "tag_bias": ['river'],
        "rarity": "common",
        "base_value": 1.0,
        "weight": 1.0,
        "desc": "Edible fungi that thrive in darkness and shade."
    },
    "fish": {
        "type": "food",
        "terrain_bias": ['riverside', 'coastal', 'deep_water'],
        "tag_bias": ['lake'],
        "rarity": "common",
        "base_value": 1.2,
        "weight": 0.8,
        "desc": "Common food source near water bodies."
    },
    "meat": {
        "type": "food",
        "terrain_bias": ['plains', 'forest', 'mountain', 'riverside', 'wetlands'],
        "tag_bias": [],
        "rarity": "common",
        "base_value": 1.5,
        "weight": 1.2,
        "desc": "Protein-rich staple, perishable."
    },
    "fruit": {
        "type": "food",
        "terrain_bias": ["mountain", "oasis"],
        "tag_bias": [],
        "rarity": "rare",
        "base_value": 3.0,
        "weight": 0.5,
        "desc": "Rare exotic fruit with healing properties."
    },

    # --- Materials ---------------------------------------------------------

    "clay": {
        "type": "material",
        "terrain_bias": ["riverside", "wetlands"],
        "tag_bias": ['lake'],
        "rarity": "common",
        "base_value": 1.0,
        "weight": 1.5,
        "desc": "Clay made bricks, tiles (roofing, flooring, and walls), and pipes are common uses."
    },
    "peat": {
        "type": "material",
        "terrain_bias": ["riverside", "wetlands"],
        "tag_bias": ['lake'],
        "rarity": "common",
        "base_value": 1.0,
        "weight": 1.5,
        "desc": "It can be mixed with other soils to improve drainage and infiltration rates."
    },
    "reeds": {
        "type": "material",
        "terrain_bias": ["riverside", "wetlands"],
        "tag_bias": ['lake'],
        "rarity": "common",
        "base_value": 1.0,
        "weight": 1.5,
        "desc": "Can be stitched into mats or processed into panels for thermal insulation in walls and ceilings."
    },
    "timber": {
        "type": "material",
        "terrain_bias": ["mountain", "plains", "forest"],
        "tag_bias": [],
        "rarity": "common",
        "base_value": 1.0,
        "weight": 1.5,
        "desc": "Basic building and fuel material."
    },
    "stone": {
        "type": "material",
        "terrain_bias": ["mountain"],
        "tag_bias": [],
        "rarity": "common",
        "base_value": 0.8,
        "weight": 2.0,
        "desc": "Common construction material."
    },
    "iron": {
        "type": "material",
        "terrain_bias": ["mountain"],
        "tag_bias": [],
        "rarity": "common",
        "base_value": 2.0,
        "weight": 3.0,
        "desc": "Metal for tools and weapons."
    },
    "golden timber": {
        "type": "material",
        "terrain_bias": ["forest"],
        "tag_bias": [],
        "rarity": "rare",
        "base_value": 3.5,
        "weight": 2.0,
        "desc": "High-quality decorative construction wood."
    },

    # --- Trade goods -------------------------------------------------------
    "spices": {
        "type": "trade",
        "terrain_bias": ["dryland", "oasis"],
        "tag_bias": [],
        "rarity": "common",
        "base_value": 3.0,
        "weight": 0.3,
        "desc": "Luxury good for cultural trade routes."
    },
    "salt": {
        "type": "trade",
        "terrain_bias": ["coastal"],
        "tag_bias": [],
        "rarity": "common",
        "base_value": 1.5,
        "weight": 1.0,
        "desc": "Essential preservative and trade staple."
    },
    "iron grass": {
        "type": "trade",
        "terrain_bias": ["plains"],
        "tag_bias": [],
        "rarity": "rare",
        "base_value": 2.5,
        "weight": 0.8,
        "desc": "Hard fibrous plant traded for textiles."
    },
    "murky-eyed frog": {
        "type": "trade",
        "terrain_bias": ["wetlands", "riverside"],
        "tag_bias": [],
        "rarity": "rare",
        "base_value": 2.2,
        "weight": 0.2,
        "desc": "Rare alchemical reagent from wetlands."
    },

    # --- Cultural / luxury -------------------------------------------------
    "coral": {
        "type": "trade",
        "terrain_bias": ["coastal"],
        "tag_bias": [],
        "rarity": "rare",
        "base_value": 3.0,
        "weight": 0.3,
        "desc": "Skeletal structures of corals were highly prized for making jewelry and ornaments."
    },
    "crystallized water": {
        "type": "luxury",
        "terrain_bias": ["mountain", "oasis"],
        "tag_bias": [],
        "rarity": "rare",
        "base_value": 4.0,
        "weight": 0.1,
        "desc": "Sacred mineral sold by monks of the montane forests."
    },
    "ashen timber": {
        "type": "luxury",
        "terrain_bias": ["forest"],
        "tag_bias": [],
        "rarity": "rare",
        "base_value": 3.8,
        "weight": 1.2,
        "desc": "Dark refined wood favored for luxury furniture."
    },
    "lucid seed": {
        "type": "luxury",
        "terrain_bias": ["riverside"],
        "tag_bias": [],
        "rarity": "rare",
        "base_value": 3.2,
        "weight": 0.2,
        "desc": "Rare seed symbolizing purity and wealth."
    },
}
def GetResourceType(name: str) -> str:
    """Return the category type (material/food/trade/luxury) of a resource."""
    return RESOURCE_CATALOG.get(name, {}).get("type", "unknown")

def IsResourceType(name: str, rtype: str) -> bool:
    """Check if a resource matches a given category."""
    return RESOURCE_CATALOG.get(name, {}).get("type") == rtype

def GetResourcesByType(rtype: str) -> list[str]:
    """List all resources under a given type."""
    return [k for k, v in RESOURCE_CATALOG.items() if v.get("type") == rtype]

def GetResourceValue(name: str) -> float:
    """Return the base trade/economic value."""
    return RESOURCE_CATALOG.get(name, {}).get("base_value", 1.0)

def GetResourcesForTerrain(terrain: str) -> dict[str, float]:
    """
    Return all resources whose terrain_bias includes the given terrain.
    The weight is derived from resource base_value / weight ratio.
    """
    result = {}
    for name, data in RESOURCE_CATALOG.items():
        if terrain in data.get("terrain_bias", []):
            weight = data.get("weight", 1.0)
            value = data.get("base_value", 1.0)
            result[name] = round(value / max(0.1, weight), 2)
    return result

def GetResourcesForTile(tile) -> dict[str, float]:
    """
    Return all resources relevant to this tile, based on:
      - terrain_bias (match tile.terrain)
      - tag_bias (any tag overlap with tile.tags)

    Weight = base_value / weight (economic desirability).
    Tag-biased resources get a small multiplier.
    """
    result = {}
    tname = getattr(tile, "origin_terrain", None)
    tags = set(getattr(tile, "tags", []) or [])

    for name, data in RESOURCE_CATALOG.items():
        terrains = data.get("terrain_bias", [])
        tag_biases = set(data.get("tag_bias", []))
        matches_terrain = tname in terrains
        matches_tag = bool(tags & tag_biases)

        if not (matches_terrain or matches_tag):
            continue

        base_val = data.get("base_value", 1.0)
        weight = data.get("weight", 1.0)
        rarity = data.get("rarity", "common")

        # Tag bias gives a slight boost
        value = base_val / max(0.1, weight)
        if matches_tag:
            value *= 1.25

        # Rarity adjusts presence
        if rarity == "rare":
            value *= 0.6
        elif rarity == "uncommon":
            value *= 0.85

        result[name] = round(value, 3)

    return result