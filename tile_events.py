# directory tile_events.py
from typing import Dict, Any
from world_utils import GetActiveTiles, LogEntityEvent
from resource_catalog import GetResourcesByType, GetResourceType
from world_index_store import world_index
import json

# -------------------------------------------------------------------
# 🔖 1. Event Library
# -------------------------------------------------------------------
TILE_EVENT_LIBRARY: Dict[str, Dict[str, Any]] = {
    "market_boom": {
        "duration": 6,
        "tags": [],
        "effects": {
            "wealth_bonus": 1.05,
            # NEW: Positive shock for Trade/Luxury goods
            "commodity_shock": {
                "trade": 0.05,  # Small boost to trade commodity values
                "luxury": 0.03  # Small boost to luxury commodity values
            }
        },
        "desc": "Trade activity surges; wealth increases slightly each tick.",
    },
    "common_raid": {
        "duration": 3,
        "tags": [],
        "effects": {"supply_drain": 5},
        "desc": "Bandits raid the settlement, stealing supplies.",
    },
    "festival": {
        "duration": 4,
        "tags": [],
        "effects": {"wealth_bonus": 1.02, "pop_growth": 1.001},
        "desc": "A local celebration boosts happiness and mild economic growth.",
    },
    "drought": {
        "duration": 8,
        "tags": ["water_crisis"], # Add a persistent tag for narrative/AI awareness
        "effects": {
            "supply_drain": 3,
            "wealth_bonus": 0.97,
            # NEW: Negative shock for Food items
            "commodity_shock": {
                "food": -0.2, # Reduces food commodity value by 0.2 per tick
                "material": -0.05 # Minor reduction in material harvest
            }
        },
        "desc": "Water shortage reduces crop yield and economic activity.",
    },
    "common_trade_mission": {
        "duration": 5,
        "tags": [],
        "effects": {"wealth_bonus": 1.1, "supply_bonus": 2},
        "desc": "Caravans bring wealth and goods from neighboring regions.",
    },
    "trade_mission": {
        "duration": 5,
        "tags": [],
        "effects": {"wealth_bonus": 1.1, "supply_bonus": 2},
        "desc": "Caravans bring wealth and goods from neighboring regions.",
    },
    "send_aid": {
        "duration": 100,
        "tags": ["aid_sent"],
        "effects": {},
        "desc": "Caravans bring aid and relief to those who need.",
    },
    "request_aid": {
        "duration": 100,
        "tags": ["aid_requested"],
        "effects": {},
        "desc": "This settlement facing deficit in supplies, asking aid from other neighbors.",
    },
    "forest_bloom": {
        "duration": 4,
        "tags": ["blooming"],
        "effects": {"eco_bonus": {"producers": 1.2, "herbivores": 1.05}},
        "desc": "Flora thrives, boosting producers and herbivores temporarily."
    },
    "predator_surge": {
        "duration": 3,
        "tags": ["blooming"],
        "effects": {"eco_bonus": {"carnivores": 1.3}, "eco_drain": {"herbivores": 0.9}},
        "desc": "Predators flourish, herbivores decline."
    },
    "ecological_collapse": {
        "duration": 5,
        "tags": [],
        "effects": {"eco_reset": True},
        "desc": "Overgrowth and imbalance lead to ecological collapse."
    },
    "do_nothing": {
        "duration": 1,
        "tags": [],
        "effects": {},
        "desc": "Placeholder for event trigger."
    },
}

# -------------------------------------------------------------------
# 🧠 2. Core API
# -------------------------------------------------------------------
def RegisterTileEvent(tile, event_name: str, duration: int, effects: Dict[str, Any], desc: str = ""):
    """
    Attach a new timed event to a tile.
    Each event entry has duration, remaining time, and a dict of effects.
    """
    tile.ensure_system("active_events", {})
    events = tile.systems["active_events"]

    events[event_name] = {
        "duration": duration,
        "remaining": duration,
        "effects": effects,
        "desc": desc or TILE_EVENT_LIBRARY.get(event_name, {}).get("desc", ""),
    }

    econ = tile.get_system("economy")
    name = econ["name"] if econ else f"Tile({tile.x},{tile.y})"

    # ▼ NEW: add event world tag if defined
    for tag in _get_event_tags(event_name):
        tile.add_tag(tag)

    LogEntityEvent(
        tile,
        "EVENT",
        f"Gained '{event_name}' for {duration} ticks)",
    )


def TriggerTileEvents(world, macro=None, clock=None, region=None):
    current_tick = clock.global_tick if clock else 0

    for tile in GetActiveTiles(world, "economy"):
        econ = tile.get_system("economy")
        if not econ:
            continue

        # --- Step 1: Activate due scheduled events -----------------------
        scheduled = tile.get_system("scheduled_events") or []
        if scheduled:
            due_events = [ev for ev in scheduled if ev["start_tick"] <= current_tick]
            for ev in due_events:
                TriggerEventFromLibrary(tile, ev["event_name"])

            # Remove activated ones
            tile.systems["scheduled_events"] = [
                ev for ev in scheduled if ev["start_tick"] > current_tick
            ]

        # --- Step 2: Process active events -------------------------------
        events = tile.get_system("active_events")
        if not events:
            continue

        expired = []
        for event_name, data in events.items():
            effects = data.get("effects", {})
            _apply_tile_event_effects(tile, econ, effects)
            data["remaining"] -= 1

            if data["remaining"] <= 0:
                expired.append(event_name)

        for e in expired:
            del events[e]

            # Clean up tags using helper
            for t in _get_event_tags(e):
                tile.remove_tag(t)

            # print(f"[Expire] {econ['name']} '{e}' ended")

        price = econ.get("price_multiplier", 1.0)

        # Optional narrative hooks:
        # active = tile.get_system("active_events") or {}
        #
        # if price > 2.5 and "market_boom" not in active:
        #     TriggerEventFromLibrary(tile, "market_boom")
        #
        # if price < 0.7 and "festival" not in active:
        #     TriggerEventFromLibrary(tile, "festival")


# -------------------------------------------------------------------
# ⚙️ 3. Internal Effect Logic
# -------------------------------------------------------------------
def _clear_event_tags(tile, event_name):
    tag = TILE_EVENT_LIBRARY.get(event_name, {}).get("tag")
    if tag:
        tile.remove_tag(tag)

def _get_event_tags(event_name):
    data = TILE_EVENT_LIBRARY.get(event_name, {})
    if "tags" in data:
        return data["tags"]
    if "tag" in data and data["tag"]:
        return [data["tag"]]
    return []

def _apply_tile_event_effects(tile, econ, effects):
    """
    Generic handler for all per-tick effects.
    Extendable: just add new effect keywords here.
    """
    if "wealth_bonus" in effects:
        econ["wealth"] *= effects["wealth_bonus"]

    if "commodity_shock" in effects:
        shocks = effects["commodity_shock"]
        subs = econ.get("sub_commodities", {})

        for name, value in subs.items():
            # Determine the resource category (e.g., 'food', 'material')
            category = GetResourceType(name)  # Uses imported GetResourceType

            # Check if this category has a shock defined in the event
            if category in shocks:
                delta = shocks[category]

                # Apply the shock to the commodity's current value
                # Using max(0.0) prevents commodity values from going negative
                subs[name] = max(0.0, subs[name] + delta)

                # Re-attach the modified sub_commodities back to the economy system
        econ["sub_commodities"] = subs

    if "supply_bonus" in effects:
        econ["supplies"] += effects["supply_bonus"]

    if "supply_drain" in effects:
        econ["supplies"] -= effects["supply_drain"]

    if "pop_growth" in effects:
        econ["population"] = int(econ["population"] * effects["pop_growth"])

    if "eco_bonus" in effects:
        eco = tile.get_system("eco")
        if eco:
            for key, mult in effects["eco_bonus"].items():
                eco[key] = eco.get(key, 0.0) * mult
            tile.attach_system("eco", eco)

    if "eco_drain" in effects:
        eco = tile.get_system("eco")
        if eco:
            for key, mult in effects["eco_drain"].items():
                eco[key] = eco.get(key, 0.0) * mult
            tile.attach_system("eco", eco)

    if "eco_reset" in effects:
        tile.attach_system("eco", {"producers": 100, "herbivores": 10, "carnivores": 2})


# -------------------------------------------------------------------
# 💡 4. Helper for One-Line Trigger
# -------------------------------------------------------------------
def TriggerEventFromLibrary(tile, event_name):
    from entities.payload_entity import CreatePayloadEntity
    from trade_routes import GenerateTradeRoutes
    from world_utils import GetActiveTiles

    # NON-PAYLOAD EVENTS → normal behavior
    if event_name not in ["trade_mission", "send_aid", "raid"]:
        data = TILE_EVENT_LIBRARY[event_name]
        RegisterTileEvent(tile, event_name, data["duration"], data["effects"], data.get("desc",""))
        return

    # ==== PAYLOAD EVENT ====
    LogEntityEvent(
        tile,
        "EVENT",
        f"Triggering incoming event {event_name}.",
    )

    # ---------------------------------------------
    # 1. Acquire world reference safely
    # ---------------------------------------------
    world = getattr(tile, "index", None)
    world = getattr(world, "world", None)
    if world is None:
        print("[DEBUG:PAYLOAD] ERROR: Cannot determine world reference")
        return

    # ---------------------------------------------
    # 2. Determine destination
    # Priority:
    #   A) Explicit override sender_tile.temp_dest (used in tests)
    #   B) Nearest economy tile (AI default behavior)
    # ---------------------------------------------
    forced_dest = getattr(tile, "temp_dest", None)

    if forced_dest:
        dest = forced_dest
    else:
        # Find nearest economy tile
        candidates = GetActiveTiles(world, "economy")
        dest = None
        best = None
        for t in candidates:
            if t is tile:
                continue
            d = (t.x - tile.x) ** 2 + (t.y - tile.y) ** 2
            if best is None or d < best:
                best = d
                dest = t

    if dest is None:
        print("[DEBUG:PAYLOAD] No valid destination")
        return

    # ---------------------------------------------
    # 3. Get sender/receiver settlement IDs
    # ---------------------------------------------
    sender_id = tile.get_system("economy")["id"]
    receiver_id = dest.get_system("economy")["id"]

    # ---------------------------------------------
    # 4. Look up trade routes from meta["trade_links"]
    # ---------------------------------------------
    meta = world[0][0].get_system("meta")
    trade_links = meta.get("trade_links", {})

    paths = trade_links.get(sender_id, [])
    route_entry = next((r for r in paths if r["partner"] == receiver_id), None)

    if route_entry:
        routes = route_entry["path"]

        LogEntityEvent(
            tile,
            "EVENT:PAYLOAD",
            f"Using trade route: {sender_id} → {receiver_id}.",
            target_entity=dest
        )
    else:
        # -----------------------------------------
        # 5. Fallback: Bresenham-style straight line
        # -----------------------------------------
        print("[payload] Trade route not found. Using fallback.")
        routes = []
        sx, sy = tile.x, tile.y
        dx, dy = dest.x, dest.y
        steps = max(abs(dx - sx), abs(dy - sy))
        for i in range(1, steps + 1):
            nx = int(round(sx + (dx - sx) * (i / steps)))
            ny = int(round(sy + (dy - sy) * (i / steps)))
            routes.append(world[ny][nx])

    LogEntityEvent(
        tile,
        "EVENT:PAYLOAD",
        f"Payload event exist as {event_name}.",
        target_entity=dest
    )
    # Payload data presets
    if event_name == "trade_mission":
        payload_data = {"type": "trade_caravan", "supplies": 5, "wealth": 2, "sub_commodities": {}, "relationship_mod": 2}

    elif event_name == "send_aid":
        payload_data = {"type": "aid_shipment", "supplies": 5, "wealth": 0, "sub_commodities": {"meat": 0.1}, "relationship_mod": 2}

    else:  # raid
        payload_data = {"type": "raid_party", "supplies": 0, "wealth": -8, "sub_commodities": {}, "relationship_mod": -10}

    # Find a sender settlement entity
    sender_entity = None
    for ent in tile.entities:
        if ent.type == "settlement_ai":
            sender_entity = ent
            break

    LogEntityEvent(
        tile,
        "EVENT:PAYLOAD",
        f"Checking sender entity on tile event.",
        target_entity=dest
    )

    payload = CreatePayloadEntity(world, tile, dest, payload_data, routes, sender_entity)

    tile.entities.append(payload)
    if not hasattr(tile, "payloads"):
        tile.payloads = []
    tile.payloads.append(payload)

    LogEntityEvent(
        tile,
        "EVENT:PAYLOAD",
        f"{event_name} dispatched from ({tile.x},{tile.y}) → ({dest.x},{dest.y}).",
        target_entity=dest
    )


def ScheduleTileEvent(tile, event_name: str, start_tick: int):
    """
    Schedule a new tile event (from TILE_EVENT_LIBRARY) to trigger at a specific future world tick.

    Example:
        ScheduleTileEvent(tile, "drought", start_tick=40)
    """
    # Validate that the event exists
    if event_name not in TILE_EVENT_LIBRARY:
        print(f"[Warning] Unknown event '{event_name}' — cannot schedule.")
        return

    data = TILE_EVENT_LIBRARY[event_name]

    # Prepare tile system
    existing = tile.get_system("scheduled_events")

    if existing is None or not isinstance(existing, list):
        tile.attach_system("scheduled_events", [])
        scheduled = tile.get_system("scheduled_events")
    else:
        scheduled = existing

    # Store schedule entry
    scheduled.append({
        "event_name": event_name,
        "start_tick": start_tick,
        "duration": data["duration"],
        "effects": data["effects"],
        "desc": data.get("desc", "")
    })

    econ = tile.get_system("economy")
    name = econ["name"] if econ else f"Tile({tile.x},{tile.y})"
    print(f"[Scheduled] {name} → '{event_name}' at tick {start_tick}")
