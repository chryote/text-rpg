# directory tile_memory.py
from typing import Any, Dict
from collections import deque

def EnsureTileMemory(tile):
    return tile.ensure_system("memory", {
        "history": [],
        "metrics": {"temperature": [], "supplies": [], "wealth": [], "sub_commodities": {}},
        "config": {"max_length": 30}
    })

def SnapshotTileState(tile, tick: int):
    mem = tile.ensure_system("memory", {
        "econ": {
            "supplies": deque(maxlen=30),
            "wealth": deque(maxlen=30),
            "population": deque(maxlen=30),
            "delta": {}
        },
        "climate": {
            "temp": deque(maxlen=30),
            "rain": deque(maxlen=30)
        },
        "tags": set(),
        "tick": 0
    })

    econ = tile.get_system("economy") or {}
    clim = tile.get_system("climate_map") or {}

    supplies = econ.get("supplies", 0)
    wealth = econ.get("wealth", 0)
    pop = econ.get("population", 0)
    temp = clim.get("temperature", 0)
    rain = clim.get("rainfall", 0)

    econ_mem = mem["econ"]
    climate_mem = mem["climate"]

    # record history
    econ_mem["supplies"].append(supplies)
    econ_mem["wealth"].append(wealth)
    econ_mem["population"].append(pop)
    climate_mem["temp"].append(temp)
    climate_mem["rain"].append(rain)

    # compute last delta
    if len(econ_mem["supplies"]) >= 2:
        econ_mem["delta"] = {
            "supplies": round(econ_mem["supplies"][-1] - econ_mem["supplies"][-2], 3),
            "wealth": round(econ_mem["wealth"][-1] - econ_mem["wealth"][-2], 3)
        }

    mem["tags"] = set(tile.tags)
    mem["tick"] = tick
    tile.attach_system("memory", mem)


def _flatten_tile_state(tile) -> Dict[str, Any]:
    flat = {}
    for sys_name in ["eco", "economy", "weather", "humidity", "soil", "climate_map"]:
        sys_data = tile.get_system(sys_name)
        if not sys_data:
            continue
        for k, v in sys_data.items():
            if isinstance(v, (int, float, str, bool)):
                flat[f"{sys_name}.{k}"] = v

    flat["tags"] = sorted(tile.tags)
    return flat


def _diff_snapshots(prev: Dict[str, Any], curr: Dict[str, Any]) -> Dict[str, Any]:
    diff = {}
    for key, val in curr.items():
        if key == "tick":
            continue
        if key not in prev:
            diff[key] = val
        else:
            pval = prev[key]
            if isinstance(val, (int, float)) and isinstance(pval, (int, float)):
                delta = round(val - pval, 3)
                if abs(delta) > 1e-6:
                    diff[key] = delta
            elif isinstance(val, list) and isinstance(pval, list):
                added = [t for t in val if t not in pval]
                removed = [t for t in pval if t not in val]
                if added or removed:
                    diff[key] = {"added": added, "removed": removed}
            elif val != pval:
                diff[key] = val
    return diff


def _record_metrics(tile, metrics, max_len):
    """Append rolling numerical history for economy and climate data."""
    econ = tile.get_system("economy")
    clim = tile.get_system("climate_map")

    # Temperature
    if clim and "temperature" in clim:
        metrics["temperature"].append(clim["temperature"])
        if len(metrics["temperature"]) > max_len:
            del metrics["temperature"][0]

    # Economy base stats
    if econ:
        metrics["supplies"].append(econ.get("supplies", 0))
        metrics["wealth"].append(econ.get("wealth", 0))
        if len(metrics["supplies"]) > max_len:
            del metrics["supplies"][0]
        if len(metrics["wealth"]) > max_len:
            del metrics["wealth"][0]

        # Sub commodities
        subs = econ.get("sub_commodities", {})
        for name, val in subs.items():
            arr = metrics["sub_commodities"].setdefault(name, [])
            arr.append(val)
            if len(arr) > max_len:
                del arr[0]


def GetTileHistory(tile, last_n: int = 10):
    memory = tile.get_system("memory")
    if not memory:
        return []
    return memory["history"][-last_n:]


def GetTileMetrics(tile):
    memory = tile.get_system("memory")
    if not memory:
        return {}
    return memory["metrics"]
