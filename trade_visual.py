# directory trade_visual.py/
"""
Trade Route Visualization Helpers
Overlay trade routes on top of existing PrintWorld() grid.

Usage:
    from trade_visual import PrintTradeRoutes
    PrintTradeRoutes(world, trade_links)
"""

from texttable import Texttable
import shutil

# Optional ANSI colors

USE_COLOR = True
try:
    columns, _ = shutil.get_terminal_size()
except:
    USE_COLOR = False

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

COLOR_LIST = [
    "\033[91m", # red
    "\033[92m", # green
    "\033[94m", # blue
    "\033[95m", # magenta
    "\033[93m", # yellow
    "\033[96m", # cyan
    "\033[90m", # gray
]
RESET = "\033[0m"


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def _route_color(idx):
    if not USE_COLOR:
        return ""
    return COLOR_LIST[idx % len(COLOR_LIST)]

def _coord_map(world):
    """Build a coordinate lookup for TileState so we can check if a tile is in a route path."""
    cmap = {}
    for row in world:
        for tile in row:
            cmap[(tile.x, tile.y)] = tile
    return cmap


# ------------------------------------------------------------
# SIMPLE OVERLAY VISUALIZER
# ------------------------------------------------------------

def PrintTradeRoutes(world, trade_links, show_ids=True, show_legend=True):
    """
    Draws world map with ASCII + trade route overlays.
    Each route is drawn using a distinct color / ASCII mark.
    """

    # Build (x,y) → list of route indices
    route_map = {}
    route_info = []

    # Flatten routes
    flat_routes = []
    for sid, links in trade_links.items():
        for link in links:
            flat_routes.append(link)

    for idx, link in enumerate(flat_routes):
        color = _route_color(idx)
        route_info.append((idx, link))
        for tile in link["path"]:
            route_map.setdefault((tile.x, tile.y), []).append(idx)

    # -------------------------------------------------------
    # Print grid with overlay
    # -------------------------------------------------------
    height = len(world)
    width = len(world[0])

    print("\n=== TRADE ROUTE MAP ===")

    # Print column numbers
    print("    " + " ".join(f"{x:02}" for x in range(width)))

    for y, row in enumerate(world):
        line = []
        for tile in row:
            coord = (tile.x, tile.y)
            t = tile.terrain

            # Base map symbols
            if t == "settlement":
                base = "🏠"
            elif tile.has_tag("river"):
                base = "~"
            else:
                base = SYMBOLS.get(t, "?")

            # --- PATCH: GIVE SETTLEMENTS PRIORITY ---
            # Overlay logic
            # Always draw settlement icon first
            if tile.terrain == "settlement":
                symbol = "🏠"

            # Otherwise draw trade routes if present
            elif coord in route_map:
                rid = route_map[coord][0]
                color = _route_color(rid)
                symbol = "*" if not USE_COLOR else f"{color}*{RESET}"

            # Otherwise fall back to base map symbol
            else:
                symbol = base

            line.append(symbol)

        print(f"{y:02}  " + " ".join(line))

    # -------------------------------------------------------
    # Legend
    # -------------------------------------------------------
    if show_legend:
        print("\n=== TRADE ROUTE LEGEND ===")
        for idx, link in enumerate(flat_routes):
            A = link["path"][0]
            B = link["path"][-1]
            color = _route_color(idx)
            name = f"Route {idx}: ({A.x},{A.y}) → ({B.x},{B.y})"
            val = link["value"]
            risk = link["risk"]

            if USE_COLOR:
                print(f"{color}*{RESET} {name} | value={val:.2f} risk={risk:.2f}")
            else:
                print(f"* {name} | value={val:.2f} risk={risk:.2f}")
