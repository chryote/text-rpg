INSIDE DIRECTORY docs/
# 🌍 Project Style Guide — Text-Based RPG Simulation

> A unified structure and naming convention for world generation, simulation, and AI systems.

---

## 🧱 Core Philosophy

This project uses a **modular simulation architecture**, where each module (e.g., `worldgen`, `ecosystem`, `economy`, `behavior`) contains:
- **Procedural systems** — high-level world steps  
- **Data utilities** — low-level helpers  
- **Simulation loops** — tick-based or event-driven  
- **Domain classes** — entities, time, and AI behavior

We use a **hybrid naming convention** for clarity and expressiveness:
- **PascalCase** → major systems or pipeline steps  
- **snake_case** → helpers and internal logic  
- **ALL_CAPS** → global constants  

This keeps high-level flows readable like English, while staying Pythonic under the hood.

---

## 🧩 1. File & Module Structure

Each module represents one conceptual system:
````
project_root/
│

├── worldgen.py # Terrain, climate, biomes, rivers, regions

├── ecosystem.py # Flora/fauna, trophic levels

├── worldsim.py # Daily/seasonal updates, weather, ecology

├── behavior.py # NPC AI, behavior trees

├── economy.py # Village production, consumption, logistics

├── time_system.py # Global + local tick management

├── main.py # World creation & entrypoint

└── docs/

    └── ProjectStyleGuide.md
````

## 🧭 2. Naming Conventions

| Category | Convention | Example                                             | Notes |
|-----------|-------------|-----------------------------------------------------|--------|
| **Classes** | PascalCase | `TimeSystem`, `WorldClock`, `NPCBehaviorTree`       | Data or system objects |
| **Top-level pipeline functions** | PascalCase | `GenerateWorld`, `DetectRegions`, `SimulateEconomy` | Used in main pipelines |
| **Local helpers / utilities** | snake_case | `get_neighbors`, `calculate_diffusion`              | Internal logic |
| **Private helpers** | _snake_case | `_ensure_tags_list`, `_find_lowest_neighbor`        | Not imported elsewhere |
| **Constants / tables** | ALL_CAPS | `SYMBOLS`, `SPECIES`                                | Immutable data |
| **Global variables** | lowercase | `rng`, `world_time`, `master_seed`                  | Avoid when possible |
| **Data keys (dicts)** | lowercase strings | `"terrain"`, `"tags"`, `"eco"`                      | Avoid camelCase keys |

---

## 🕰️ 3. Time & Simulation Convention

- 1 **global_tick** = 1 in-game day  
- 24 **local_ticks** = 24 in-game hours  
- `TimeSystem` orchestrates hourly (`local`) and daily (`global`) events.  
- Use `GetTimeState(hour)` for descriptive states:
  - dawn, morning, afternoon, evening, dusk, night

Example:

```python
def hourly_update(clock, _): ...
def daily_update(clock, _): ...
```

## 🌍 4. Worldgen & Simulation Pipeline

Each worldgen step should read like a clear recipe:
````
world = GenerateWorld(rng)

world = AssignClimate(world, rng)

world = AddDrylands(world, rng)

world = AddOases(world, rng)

world = DetectRegions(world)

world = DeriveBiome(world)

world, macro = DetectRegions(world)

macro = AssignRegionNames(macro)

world = TagRivers(world, macro)

world = SeedFloraFauna(world, rng)
````
Each function:

1. Receives and returns world
2. Does one task only
3. Is deterministic if given the same RNG seed

## 🧮 5. Data Model Standards
## Tiles

````
{
    "x": int,
    "y": int,
    "terrain": str,
    "elevation": float,
    "tags": list[str],
    "climate": str,
    "biome": str (optional),
    "eco": dict (optional),
    "regions": dict (optional)
}

````
## Regions
````
{
    "id": int,
    "terrain": "continent" | "forest_cluster" | "mountain_cluster" | ...,
    "tiles": [(x, y), ...],
    "area": int,
    "avg_elevation": float,
    "climate_distribution": dict[str, float],
    "name": str
}

````

## Settlements
````
{
    "id": int,
    "name": str,
    "position": (x, y),
    "population": int,
    "supplies": float,
    "production": float,
    "sub_commodities": dict[str, float],
    "biome": str
}

````

## ⚙️ 6. Event System Conventions
Use the ``TimeSystem`` to manage world events:
````
time_system.subscribe("local", hourly_behavior_update)
time_system.subscribe("global", daily_world_update)
time_system.subscribe_every(6, weather_front_update)
````
Each callback has the signature:
````
def callback(clock: WorldClock, region=None) -> None:
    ...
````

## 💾 7. RNG & Determinism
Always use a seeded RNG instance:
````
rng = random.Random(master_seed)
world = GenerateWorld(rng)
````
This ensures reproducible worlds and simulations.

## 🧠 8. Function Prefix Patterns

| Prefix     | Purpose                   | Example                                 |
| ---------- | ------------------------- | --------------------------------------- |
| `Generate` | Create new data           | `GenerateWorld`, `GenerateRivers`       |
| `Assign`   | Attach attributes         | `AssignClimate`, `AssignSubCommodities` |
| `Add`      | Modify or inject features | `AddDrylands`, `AddOases`               |
| `Detect`   | Cluster or analyze        | `DetectRegions`, `DetectAndTagLakes`    |
| `Tag`      | Mark data                 | `TagRivers`, `TagTradeRoutes`           |
| `Simulate` | Advance systems over time | `SimulateEconomy`, `SimulateEcosystem`  |
| `Update`   | Recompute or refresh      | `UpdateWeather`, `UpdateEcosystem`      |
| `Get`      | Retrieve information      | `GetNeighbors`, `GetTimeState`          |

## 🧩 9. Output & Debugging

| Function                 | Purpose                         |
| ------------------------ | ------------------------------- |
| `PrintWorld()`           | Minimal display                 |
| `PrintWorldWithCoords()` | Debug coordinates               |
| `Plot...()`              | Visual analytics via Matplotlib |

Keep Unicode/emoji output only in visualization,
not in computational or serialization layers.
