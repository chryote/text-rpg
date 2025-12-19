# directory trade_routes.py/
"""
Simple Trade Route System (Phase 1)
-----------------------------------

Features:
- Collect Settlement Profiles
- Find Trade Partners
- Compute Trade Value
- Cheap A* / heuristic pathing
- Route risk evaluation
- Settlement prosperity + bandit tags
- Integration hooks with SimulateSettlementEconomy

This module assumes:
- TileState
- world_utils helpers
- world_index_store.world_index
- economy systems (supplies, wealth, sub_commodities)
"""

from math import sqrt
from collections import defaultdict
import heapq
from itertools import count
import math

from world_utils import GetNearestTileWithSystem, GetTilesWithinRadius, GetActiveTiles, LogEntityEvent
import world_index_store

# -------------------------------------------------------------------
# 0. Helpers for Entity Access
# -------------------------------------------------------------------

def get_settlement_ai(tile):
    """Safely fetch the primary Settlement AI entity from the tile."""
    # Assumes settlement_ai is on the tile if tile.terrain is "settlement"
    for entity in tile.entities:
        if entity.type == "settlement_ai":
            return entity
    return None

# -------------------------------------------------------------------
# 1. Settlement Profile Extraction
# -------------------------------------------------------------------

def CollectSettlementProfiles(world):
    """
    Returns:
        profiles: dict[settlement_id] = {
            'tile': TileState,
            'exports': {...},
            'imports': {...},
            'production': float,
            'consumption': float,
            'population': int,
            'wealth': float,
            'supplies': float
        }
    """
    profiles = {}
    widx = world_index_store.world_index

    for tile in widx.with_system("economy"):
        econ = tile.get_system("economy")
        sid = econ["id"]

        subs = econ.get("sub_commodities", {})
        exports = {k: v for k, v in subs.items() if v > 1.0}
        imports = {}

        # naive demand table
        pop = econ["population"]
        base_demand = {
            "grain": pop * 0.02,
            "meat": pop * 0.015,
            "fish": pop * 0.01,
            "timber": pop * 0.005,
            "stone": pop * 0.003,
            "iron": pop * 0.002,
        }

        for rname, demand_value in base_demand.items():
            have = subs.get(rname, 0)
            if have < demand_value * 0.5:
                imports[rname] = demand_value - have

        profiles[sid] = {
            "tile": tile,
            "exports": exports,
            "imports": imports,
            "population": pop,
            "wealth": econ["wealth"],
            "supplies": econ["supplies"],
            "production": econ.get("production", 0),
            "consumption": econ.get("consumption", 0),
            "prosperity": econ.get("prosperity", 0),
        }

    return profiles


# -------------------------------------------------------------------
# 2. Find Trade Partners
# -------------------------------------------------------------------

def FindTradePartners(world, profiles, max_partners=3, search_radius=60):
    """
    For each settlement, find closest complementary partners,
    modulating the score by Affinity and Cautiousness/Distance.

    Returns:
        partners[sid] = list of other settlement_ids
    """
    widx = world_index_store.world_index
    partners = defaultdict(list)

    sids = list(profiles.keys())

    for sid, profile in profiles.items():
        tile = profile["tile"]
        x, y = tile.x, tile.y

        # 1. Get Affinity/Caution details for Settlement A
        entityA = get_settlement_ai(tile)
        if not entityA:
            continue

        cautious_trait = entityA.get("personality").get("cautious")
        rel_comp_A = entityA.get("relationship")

        # Max distance proxy used to normalize the cautious penalty
        max_distance_proxy = search_radius * 0.75

        # scan nearby tiles for settlement candidates
        candidates = []
        nearby = widx.tiles_within_radius(x, y, search_radius)
        for t in nearby:
            econ = t.get_system("economy")
            if not econ:
                continue
            osid = econ["id"]
            if osid == sid:
                continue
            candidates.append((osid, t))

        # score candidates by complementarity + distance + affinity + caution
        scored = []
        for osid, otile in candidates:
            d_raw = (otile.x - x) ** 2 + (otile.y - y) ** 2
            d_euc = d_raw ** 0.5
            if d_euc == 0:
                continue

            # original dicts
            expA = profile["exports"]
            impA = profile["imports"]
            expB = profiles[osid]["exports"]
            impB = profiles[osid]["imports"]

            # compute how much A's exports match B's imports and vice versa
            match_A_to_B = sum(min(expA.get(r, 0), impB.get(r, 0)) for r in expA)
            match_B_to_A = sum(min(expB.get(r, 0), impA.get(r, 0)) for r in expB)

            complement_value = match_A_to_B + match_B_to_A
            if complement_value == 0:
                continue

            # --- REFACTORED: Affinity Factor (Using VAS Relationship Valence) ---
            entityB = get_settlement_ai(otile)
            if entityB and rel_comp_A:
                # Use the new get_rv method which returns a float between -1.0 and 1.0
                #
                rv_score = rel_comp_A.get_rv(entityB.id)

                # Maps [-1.0, 1.0] to a multiplier of [0.5, 1.5]
                # A neutral relationship (0.0) results in a 1.0 multiplier.
                affinity_factor = 1.0 + (rv_score * 0.5)
            else:
                affinity_factor = 1.0

            # --- NEW: Cautious Distance Penalty ---
            # (Note: Personality refactor also changes 'cautious' to 'anxiety_sensitivity' or similar,
            # but if you keep 'cautious' as a custom trait, ensure it's pulled from the
            # new PersonalityComponent)
            cautious_trait = entityA.get("personality").get("anxiety_sensitivity")  # refactored trait
            cautious_penalty_factor = 1.0 + (cautious_trait * d_euc) / max(1.0, max_distance_proxy)

            # --- NEW: Final Score Calculation ---
            # Score = (ComplementValue * Affinity) / (Distance * Penalty)
            score = (complement_value * affinity_factor) / (d_euc * cautious_penalty_factor)

            scored.append((score, osid))

        scored.sort(reverse=True)
        partners[sid] = [pid for _, pid in scored[:max_partners]]

    return partners


# -------------------------------------------------------------------
# 3. Compute Trade Value
# -------------------------------------------------------------------

def ComputeTradeValue(profileA, profileB):
    """
    Simple symmetric score:
    - how much A exports that B imports
    - how much B exports that A imports
    - scaled by supply/wealth factors
    """
    expA = profileA["exports"]
    expB = profileB["exports"]
    impA = profileA["imports"]
    impB = profileB["imports"]

    valA = sum(v for k, v in expA.items() if k in impB)
    valB = sum(v for k, v in expB.items() if k in impA)

    base = valA + valB
    if base <= 0:
        return 0

    wealth_mod = (profileA["wealth"] + profileB["wealth"]) / 200
    supply_mod = (profileA["supplies"] + profileB["supplies"]) / 200

    return base * (0.5 + wealth_mod + supply_mod)


# -------------------------------------------------------------------
# 4. Pathfinding (Cheap A* with terrain weight)
# -------------------------------------------------------------------

def tile_cost(tile):
    """Simple tile-based movement cost."""
    terr = tile.movement_cost or 1.5
    return terr
    # if terr in ["mountain"]:
    #     return 4
    # if terr in ["forest"]:
    #     return 2
    # if terr in ["wetlands"]:
    #     return 3
    # if terr in ["plains", "coastal"]:
    #     return 1
    # if terr in ["oasis", "dryland"]:
    #     return 2
    # return 1.5


def FindRoute(world, start, goal, max_len=2000):
    """
    Safe A* pathfinder:
    - Uses (priority, counter, tile) to avoid TileState comparisons
    - Same behavior as before, no logic changes
    """

    H = len(world)
    W = len(world[0])

    def neighbors(t):
        x, y = t.x, t.y
        res = []
        for ny in range(max(0, y - 1), min(H, y + 2)):
            for nx in range(max(0, x - 1), min(W, x + 2)):
                if nx == x and ny == y:
                    continue
                res.append(world[ny][nx])
        return res

    # <<< FIX HERE → counter for heap entries >>>
    counter = count()

    # heap items: (priority, counter, tile)
    open_heap = []
    heapq.heappush(open_heap, (0, next(counter), start))

    came = {}
    gscore = {start: 0}

    while open_heap and len(came) < max_len:
        _, _, current = heapq.heappop(open_heap)

        if current == goal:
            # reconstruct path
            path = [current]
            while current in came:
                current = came[current]
                path.append(current)
            return list(reversed(path))

        for nb in neighbors(current):
            cost = tile_cost(nb)
            new_g = gscore[current] + cost

            if nb not in gscore or new_g < gscore[nb]:
                gscore[nb] = new_g
                priority = new_g + ((nb.x - goal.x)**2 + (nb.y - goal.y)**2)**0.5
                heapq.heappush(open_heap, (priority, next(counter), nb))
                came[nb] = current

    return None


# -------------------------------------------------------------------
# 5. Route Risk Evaluation
# -------------------------------------------------------------------

def EvaluateRouteRisk(path):
    """
    Fully eco-aware route risk evaluation.

    Considers:
    - biome danger
    - weather instability
    - humidity extremes
    - soil fertility (low soil = barren, high soil = safe farmland)
    - eco trophic imbalance (predators)
    - eco_risk system from new ecosystem engine
    - special eco events (forest_bloom, predator_surge, ecological_collapse)
    """

    risk = 0.0

    for tile in path:
        tags = tile.tags

        # 1️⃣ Biome-based risk
        biome = tile.biome or ""
        if biome in ["forest", "rainforest"]:
            risk += 0.5
        if biome in ["desert", "semi_arid", "scrubland", "cold_steppe"]:
            risk += 0.4
        if biome in ["wetland", "mangrove"]:
            risk += 0.6
        if biome in ["savanna"]:
            risk += 0.2
        if biome in ["mountain", "alpine", "montane_forest"]:
            risk += 0.7

        # 2️⃣ Weather severity
        wsys = tile.get_system("weather") or {}
        w_state = wsys.get("state", "")
        if w_state == "storm":
            risk += 0.7
        elif w_state == "rain":
            risk += 0.2
        elif w_state == "drought":
            risk += 0.3

        # 3️⃣ Humidity extremes
        hum = tile.get_system("humidity") or {}
        H = hum.get("current", 0.5)
        if H < 0.2:
            risk += 0.3    # dehydration hazard
        if H > 0.85:
            risk += 0.4    # swampy, disease

        # 4️⃣ Soil fertility
        soil = tile.get_system("soil") or {}
        fert = soil.get("fertility", 0.5)
        if fert < 0.25:
            risk += 0.3  # barren land, few safe havens
        elif fert > 0.7:
            risk -= 0.2  # farmland tends to be safer

        # 5️⃣ Ecosystem predator-heavy risk
        eco = tile.get_system("eco") or {}
        carn = eco.get("carnivores", 0)
        herb = eco.get("herbivores", 1)
        predator_ratio = carn / max(herb, 1)
        if predator_ratio > 1.0:
            risk += predator_ratio * 0.6

        # 6️⃣ Eco-risk system (from new simulation)
        eco_r = tile.get_system("eco_risk") or {}
        risk += eco_r.get("value", 0)

        # 7️⃣ Eco EVENTS (strong influence)
        if "forest_bloom" in tags:
            risk -= 0.4  # lush → safer
        if "predator_surge" in tags:
            risk += 1.2  # extremely dangerous
        if "ecological_collapse" in tags:
            risk += 1.5  # unpredictable

        # 8️⃣ Bandit logic / tile tags
        if "bandit_settlement" in tags:
            risk += 1.0

    return max(risk, 0.0)



# -------------------------------------------------------------------
# 6. Generate Settlement Tags
# -------------------------------------------------------------------

def TagSettlements(world, profiles, routes):
    """
    Assign prosperity, crisis, trade-hub and bandit tags.
    """
    widx = world_index_store.world_index

    for sid, prof in profiles.items():
        tile = prof["tile"]
        econ = tile.get_system("economy")

        wealth = prof["wealth"]
        supplies = prof["supplies"]
        pop = prof["population"]
        prosperity = prof["prosperity"]

        # basic prosperity
        # prosperity = wealth + supplies - pop * 0.2
        # econ["prosperity"] = prosperity

        # remove old derived tags first
        for tag in ["prosperous", "struggling", "supplies_deficit",
                    "trade_hub", "bandit_settlement", "bandit_infested_settlement"]:
            if tag in tile.tags:
                tile.tags.remove(tag)

        # assign prosperity-level tags
        if prosperity > 200:
            tile.add_tag("prosperous")
        elif prosperity < 40:
            tile.add_tag("struggling")
        if supplies < pop * 0.5:
            tile.add_tag("supplies_deficit")

        # trade hub: many connections
        if len(routes.get(sid, [])) >= 3:
            tile.add_tag("trade_hub")

    # --- Dynamic Conflict Trigger Sophistication ---
    for sid, prof in profiles.items():
        tile = prof["tile"]
        econ = tile.get_system("economy")
        prosperity = econ.get("prosperity", 0)

        # 1. Check for local risk factors
        local_risk_score = 0

        # Risk Factor A: High outgoing route risk (External Threat)
        links = routes.get(sid, [])
        avg_route_risk = sum(link["risk"] for link in links) / max(1, len(links))
        if avg_route_risk > 2.0:  # High risk threshold
            local_risk_score += 1

        # Risk Factor B: Nearby Hostile Relations (Social Conflict)
        entityA = get_settlement_ai(tile)
        if entityA:
            rel_comp = entityA.get("relationship")
            if rel_comp:
                for score in rel_comp.table.values():
                    if score['rv'] < -0.5 and score['rs'] < -0.5:  # Strong rivalry (potential conflict trigger)
                        local_risk_score += 1
                        break  # Only need one hostile neighbor to trigger this factor

        # Risk Factor C: High wilderness exposure (Local Environment)
        neighbor_tiles = GetTilesWithinRadius(world, tile.x, tile.y, radius=3)
        # Wilderness: areas not immediately next to other settlements or easy movement tiles
        wild_count = sum(1 for t in neighbor_tiles if t.terrain not in ["settlement", "coastal", "plains", "riverside"])

        if wild_count > 5:  # High wilderness exposure threshold
            local_risk_score += 1

        # Final Tag Assignment: Bandit presence requires low prosperity/vulnerability AND enough risk factors
        if prosperity < 50 and local_risk_score >= 2:
            tile.add_tag("bandit_infested_settlement")


# -------------------------------------------------------------------
# 7. Full Pipeline
# -------------------------------------------------------------------

# -------------------------------------------------------------------
# 7B. Fully Connected Trade Network (MST + Partner Routes)
# -------------------------------------------------------------------

def GenerateTradeRoutes(world):
    """
    Improved version:
    - Ensures that ALL settlements are connected using MST backbone.
    - Adds the original partner-based trade routes as additional edges.
    """

    profiles = CollectSettlementProfiles(world)

    # ------------------------------------------------------------------
    # STEP 1: List all settlements
    # ------------------------------------------------------------------
    settlements = list(profiles.items())  # [(sid, profile), ...]
    n = len(settlements)
    if n <= 1:
        return {}

    # ------------------------------------------------------------------
    # STEP 2: Precompute all pairwise shortest paths (or distances)
    # Using your existing A*.
    # ------------------------------------------------------------------
    distances = {}  # (sidA, sidB) -> (path, total_cost)

    def path_cost(path):
        return sum(tile_cost(t) for t in path)

    for i in range(n):
        sidA, profA = settlements[i]
        for j in range(i + 1, n):
            sidB, profB = settlements[j]
            path = FindRoute(world, profA["tile"], profB["tile"])
            if not path:
                continue
            cost = path_cost(path)
            distances[(sidA, sidB)] = (path, cost)
            distances[(sidB, sidA)] = (path, cost)

    # ------------------------------------------------------------------
    # STEP 3: Build MST using Kruskal
    # ------------------------------------------------------------------
    parent = {sid: sid for sid, _ in settlements}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra == rb:
            return False
        parent[rb] = ra
        return True

    # convert distances into edge list
    edges = []
    for (sidA, sidB), (path, cost) in distances.items():
        if sidA < sidB:  # avoid duplicates
            edges.append((cost, sidA, sidB, path))

    edges.sort(key=lambda x: x[0])  # Kruskal: sort by cost

    mst_links = defaultdict(list)

    for cost, sidA, sidB, path in edges:
        if union(sidA, sidB):
            risk = EvaluateRouteRisk(path)
            value = ComputeTradeValue(profiles[sidA], profiles[sidB])
            mst_links[sidA].append({
                "partner": sidB,
                "value": value,
                "risk": risk,
                "path": path
            })
            mst_links[sidB].append({
                "partner": sidA,
                "value": value,
                "risk": risk,
                "path": path
            })

    # ------------------------------------------------------------------
    # STEP 4: Add your existing partner-based routes as "optional extras"
    # ------------------------------------------------------------------
    partners = FindTradePartners(world, profiles)
    extra_links = defaultdict(list)

    for sid, plist in partners.items():
        A = profiles[sid]
        Atile = A["tile"]

        for osid in plist:
            B = profiles[osid]
            Btile = B["tile"]
            value = ComputeTradeValue(A, B)
            if value <= 0:
                continue

            path = FindRoute(world, Atile, Btile)
            if not path:
                continue

            risk = EvaluateRouteRisk(path)

            extra_links[sid].append({
                "partner": osid,
                "value": value,
                "risk": risk,
                "path": path
            })

    # ------------------------------------------------------------------
    # STEP 5: Merge MST backbone + extra partner routes
    # ------------------------------------------------------------------
    trade_links = defaultdict(list)

    # Always include MST backbone routes
    for sid, links in mst_links.items():
        trade_links[sid].extend(links)

    # Add the extra routes (avoid identical duplicates)
    for sid, links in extra_links.items():
        existing = {(l["partner"], tuple(l["path"])) for l in trade_links[sid]}
        for link in links:
            key = (link["partner"], tuple(link["path"]))
            if key not in existing:
                trade_links[sid].append(link)

    # ------------------------------------------------------------------
    # STEP 6: Settlement tags (unchanged)
    # ------------------------------------------------------------------
    TagSettlements(world, profiles, trade_links)

    return trade_links

# -------------------------------------------------------------------
# 8. Economy Hook: Apply trade effects
# -------------------------------------------------------------------

def ApplyTradeEffects(world):
    """
    Called each daily tick (after SimulateSettlementEconomy).
    Uses indexed trade_links and economy-tagged tiles only.
    """

    import math

    meta = world[0][0].get_system("meta")
    trade_links = meta["trade_links"]

    def diminishing(x, p=0.6):
        return x ** p

    # Build a fast lookup: econ_id -> tile
    settlement_by_id = {}
    for tile in GetActiveTiles(world, "economy"):
        econ = tile.get_system("economy")
        if econ:
            settlement_by_id[econ["id"]] = tile

    # Loop all trade links
    for sid, links in trade_links.items():

        tile = settlement_by_id.get(sid)
        if not tile:
            continue

        econ = tile.get_system("economy")
        if not econ:
            continue

        # --- TRADE VALUE -------------------------------------------------
        total_value = sum(link["value"] for link in links)
        trade_gain = diminishing(total_value, 0.7)

        price = econ.get("price_multiplier", 1.0)

        # WELFARE GAINS
        econ["wealth"] += trade_gain * 0.04 * (1.0 / price)

        # SUPPLY GAINS
        econ["supplies"] += trade_gain * 0.02 * (1.0 / price)

        # --- ROUTE RISK --------------------------------------------------
        total_risk = sum(link["risk"] for link in links)

        # mitigation based on power projection
        defense = max(1.0, econ.get("power_projection", 1.0))
        mitigation = math.sqrt(defense)

        risk_effect = total_risk / mitigation

        econ["wealth"] -= risk_effect * 0.02
        econ["supplies"] -= risk_effect * 0.015

        econ["wealth"] = max(0.0, econ["wealth"])
        econ["supplies"] = max(0.0, econ["supplies"])


def UpdateTradeNetwork(world, macro, clock, region):
    """
    Recalculate the entire trade network (partnerships, routes, values)
    periodically to reflect changes in economy, relationships, and risk.
    Runs every 7 global ticks (days).
    """

    # Rerun the full generation pipeline
    new_trade_links = GenerateTradeRoutes(world)

    # Overwrite the stored links
    meta = world[0][0].get_system("meta")
    meta["trade_links"] = new_trade_links

    LogEntityEvent(
        None,
        "TRADE NETWORK",
        f"[{clock}] Trade Network Recalculated! {len(new_trade_links)} link groups renewed.",
    )

    # print(f"[{clock}] Trade Network Recalculated! {len(new_trade_links)} link groups renewed.")

def UpdateTradeRouteRisks(world):
    """
    Recalculates the risk for all existing trade links based on the current
    state of the path tiles (weather, eco_risk, bandits, etc.).
    This should be called before ApplyTradeEffects.
    """
    # Note: world_index_store is already imported at the top of the file.

    # 1. Access the trade_links data stored in the world[0][0] meta system
    # Assuming GenerateTradeRoutes previously stored it here:
    meta = world[0][0].get_system("meta")
    trade_links = meta.get("trade_links")

    if not trade_links:
        # print("[TradeRoutes] No trade links found to update risks.")
        return

    # Use defaultdict only for temporary storage if structure needs recreation
    updated_links = defaultdict(list)

    # 2. Iterate and recalculate risk for every link
    for sid, links in trade_links.items():
        for link in links:
            # The original path (list of TileState objects) is preserved in the link
            path = link["path"]

            # Re-evaluate the risk using the dynamic state of the tiles
            new_risk = EvaluateRouteRisk(path)

            # 3. Update the risk value in the structure
            link["risk"] = new_risk

            updated_links[sid].append(link)

    # 4. Overwrite the old trade links with the newly updated one
    meta["trade_links"] = updated_links
    # print("[TradeRoutes] All route risks updated.")
