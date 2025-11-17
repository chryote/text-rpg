# directory tile_state.py
from typing import Dict, Any, Tuple, Optional, List
from collections import deque

class TileState:
    """
    Unified data model for a single world tile.
    Includes terrain, biome, mobility, entities, and subsystem (eco/economy/etc.) data.
    """

    def __init__(
        self,
        x: int,
        y: int,
        layer: str,
        elevation: float,
        terrain: str,
        climate: Optional[str] = None,
        biome: Optional[str] = None,
        origin_terrain: Optional[str] = None,
        movement_method: Optional[List[str]] = None,
        movement_cost: Optional[int] = None,
        entities: Optional[List[dict]] = None,
        tags: Optional[List[str]] = None,
        regions: Optional[dict] = None,
        systems: Optional[dict] = None,
    ):
        self.x = x
        self.y = y
        self.layer = layer
        self.region_offset = {}
        self.region_direction = {}
        self.density_from_settlement_generation = None
        self.elevation = elevation
        self.terrain = terrain
        self.climate = climate
        self.biome = biome
        self.origin_terrain = origin_terrain
        self.movement_method = movement_method or []
        self.movement_cost = movement_cost or 1
        self.entities = entities or []
        self.tags = tags or []
        self.regions = regions or {}
        self.systems = systems or {}
        self.index = None

    # --- Core utilities ----------------------------------------------------
    @property
    def pos(self) -> Tuple[int, int]:
        return (self.x, self.y)

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags

    def set_terrain(self, new_terrain):
        old = self.terrain
        self.terrain = new_terrain
        if self.index:
            self.index.register_terrain_change(self, old, new_terrain)

    def add_tag(self, tag):
        if not isinstance(tag, str):
            return
        tag = tag.strip().lower()

        if tag not in self.tags:
            self.tags.append(tag)
            if self.index:
                self.index.register_tag(self, tag)

    def remove_tag(self, tag):
        if tag in self.tags:
            self.tags.remove(tag)
            if self.index:
                self.index.unregister_tag(self, tag)

    def set_tags(self, tags: list[str]):
        """Replace tags entirely (useful for weather or biome resets)."""
        self.tags = list(dict.fromkeys(tags))  # remove dupes, preserve order

    def has_any_tag(self, *tags: str) -> bool:
        return any(t in self.tags for t in tags)

    def attach_system(self, name: str, data: dict):
        first_time = name not in self.systems
        self.systems[name] = data

        if self.index:
            if first_time:
                self.index.register_system(self, name)

    def get_system(self, name: str):
        return self.systems.get(name)

    def ensure_system(self, name: str, default: Optional[dict] = None):
        """
        Get or create a subsystem dict.
        If default is provided, it's used only when the system doesn't exist.
        """
        if name not in self.systems:
            self.systems[name] = dict(default or {})
        return self.systems[name]

    # --- Export compatibility ---------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """
        Flatten the TileState into a fully JSON-compatible dictionary form.
        Includes all core attributes, region data, and attached subsystems.
        """
        base: Dict[str, Any] = {
            "x": self.x,
            "y": self.y,
            "layer": self.layer,
            "elevation": float(self.elevation),
            "terrain": self.terrain,
            "climate": self.climate,
            "biome": self.biome,
            "origin_terrain": self.origin_terrain,
            "movement_method": list(self.movement_method),
            "movement_cost": int(self.movement_cost),
            "entities": [
                e.to_json() if hasattr(e, "to_json") else e
                for e in self.entities
            ],
            "tags": list(self.tags),
            "regions": dict(self.regions),
            "region_offset": dict(self.region_offset),
            "region_direction": dict(self.region_direction),
        }

        # Optional / derived fields
        if self.density_from_settlement_generation is not None:
            base["density_from_settlement_generation"] = float(self.density_from_settlement_generation)

        # Deep copy of all attached subsystems (eco, economy, biota, weather, meta, etc.)
        systems_dict = {}

        def _convert_serializable(obj):
            """
            Recursively convert unsupported types (deque, set) into JSON-safe structures.
            - deque → list
            - set   → sorted list (deterministic output)
            """
            if isinstance(obj, deque):
                return [_convert_serializable(v) for v in obj]
            elif isinstance(obj, set):
                return sorted(_convert_serializable(v) for v in obj)
            elif isinstance(obj, dict):
                return {k: _convert_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_convert_serializable(v) for v in obj]
            else:
                return obj

        for sys_name, sys_data in self.systems.items():
            # 🔄 Step 1: recursively convert any deque → list
            sys_data = _convert_serializable(sys_data)

            # 🔄 Step 2: proceed with normal safe serialization
            if isinstance(sys_data, (dict, list, str, int, float, bool, type(None))):
                systems_dict[sys_name] = sys_data
            else:
                try:
                    import copy
                    systems_dict[sys_name] = copy.deepcopy(sys_data)
                except Exception:
                    systems_dict[sys_name] = str(sys_data)

        # Merge systems into base (flat structure for backward compatibility)
        base.update(systems_dict)

        return base

    def __repr__(self):
        return f"Tile({self.x},{self.y},{self.terrain}, elev={self.elevation:.2f})"

    # --- Settlement economy agent --------------------------------------------
    @property
    def agent(self):
        """
        Shortcut accessor for SettlementEconomyAgent.
        Returns an agent only if this tile has an economy system (e.g., a settlement).
        """
        from economy import SettlementEconomyAgent  # ✅ moved here to avoid circular import
        econ = self.get_system("economy")
        if not econ:
            raise AttributeError(f"Tile ({self.x}, {self.y}) has no economy system — cannot use agent.")
        return SettlementEconomyAgent(self)
