# directory world_index.py/
from collections import defaultdict

class WorldIndex:
    """
    Fully corrected & optimized world index.

    Key improvements:
    - Uses sets (O(1) add/remove)
    - Supports unregister for tag/system when removed
    - Terrain changes handled correctly
    - Full rebuild() for worldgen finalization
    - Query API returns regular lists (backwards compatible)
    """

    def __init__(self, world):
        self.world = world

        # system_name -> set(tile)
        self.system_index = defaultdict(set)

        # terrain -> set(tile)
        self.terrain_index = defaultdict(set)

        # tag -> set(tile)
        self.tag_index = defaultdict(set)

        # build initial index
        self.rebuild()

    # ----------------------------------------------------------------------
    # FULL REBUILD
    # ----------------------------------------------------------------------
    def rebuild(self):
        """Full rescan of the world. Call after world generation."""
        self.system_index.clear()
        self.terrain_index.clear()
        self.tag_index.clear()

        for row in self.world:
            for tile in row:

                # systems
                for sys_name in tile.systems.keys():
                    self.system_index[sys_name].add(tile)

                # terrain
                self.terrain_index[tile.terrain].add(tile)

                # tags
                for tag in tile.tags:
                    self.tag_index[tag].add(tile)

    # ----------------------------------------------------------------------
    # UPDATE HOOKS (called by TileState)
    # ----------------------------------------------------------------------
    def register_system(self, tile, name):
        self.system_index[name].add(tile)

    def unregister_system(self, tile, name):
        s = self.system_index.get(name)
        if s:
            s.discard(tile)  # safe remove

    def register_tag(self, tile, tag):
        self.tag_index[tag].add(tile)

    def unregister_tag(self, tile, tag):
        s = self.tag_index.get(tag)
        if s:
            s.discard(tile)

    def register_terrain_change(self, tile, old, new):
        # remove from old terrain set
        if old in self.terrain_index:
            self.terrain_index[old].discard(tile)

        # add into new terrain set
        self.terrain_index[new].add(tile)

    # ----------------------------------------------------------------------
    # QUERY API (returns lists for compatibility)
    # ----------------------------------------------------------------------
    def with_system(self, system_name):
        return list(self.system_index.get(system_name, ()))

    def with_terrain(self, terrain):
        return list(self.terrain_index.get(terrain, ()))

    def with_tag(self, tag):
        return list(self.tag_index.get(tag, ()))

    def tiles_within_radius(self, center_x, center_y, radius):
        """
        Return list of tiles within Chebyshev distance radius from (center_x, center_y).
        This method needs world grid access; rely on self.world.
        """
        result = []
        H = len(self.world)
        W = len(self.world[0]) if H > 0 else 0
        for y in range(max(0, center_y - radius), min(H, center_y + radius + 1)):
            for x in range(max(0, center_x - radius), min(W, center_x + radius + 1)):
                result.append(self.world[y][x])
        return result

    def nearest_with_system(self, system_name, from_x, from_y, max_radius=50):
        """
        Find nearest tile with a specific system. Uses index fast-path then radius scan fallback.
        """
        # fast path using index sets
        tiles = list(self.system_index.get(system_name, ()))
        if tiles:
            best = min(tiles, key=lambda t: (t.x - from_x) ** 2 + (t.y - from_y) ** 2)
            return best

        # fallback expanding radius search
        for r in range(0, max_radius + 1):
            for y in range(max(0, from_y - r), min(len(self.world), from_y + r + 1)):
                for x in range(max(0, from_x - r), min(len(self.world[0]), from_x + r + 1)):
                    t = self.world[y][x]
                    if t.get_system(system_name):
                        return t
        return None