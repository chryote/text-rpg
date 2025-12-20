# entities/components/settlement_ai.py

from ..component import Component
from world_utils import GetTilesWithinRadius, GetNearestTileWithSystem, LogEntityEvent, GetActiveTiles
import behavior as bh  # your behavior.py (Node, Sequence, Selector, Status)
import world_index_store


class SettlementAIComponent(Component):
    def __init__(self):
        super().__init__("settlement_ai")
        self._bt_built = False

    def _build_behavior_tree(self):
        """
        Build a compact BT capturing:
          - defend_if_threat (bandits nearby)
          - handle_supply_crisis (increase supplies / request aid)
          - celebrate_if_prosperous (festival)
          - idle (do maintenance)
        Nodes are closures that reference self.entity
        """
        entity = self.entity

        class CheckThreat(bh.Node):
            def tick(self):
                # Now uses the unified perception blackboard
                perc = entity.get("perception")
                if not perc: return bh.Status.FAILURE

                # Check for high sensory intensity (SV) or negative intent (I_raw)
                # indicating a perceived threat
                if perc.blackboard.get("sv", 0) > 0.6 or perc.blackboard.get("i_raw", 0) < -0.4:
                    return bh.Status.SUCCESS
                return bh.Status.FAILURE

        class DefendAction(bh.Node):
            def tick(self):
                # Uses unified emotion impulse system
                emo = entity.get("emotion")
                if emo:
                    # High uncertainty and sensory impact increase arousal
                    emo.apply_impulse(dv=-0.2, da=0.4, ds=-0.3)
                entity.tile.add_tag("under_threat")
                return bh.Status.SUCCESS

        class CheckSupplyCrisis(bh.Node):
            def tick(self):
                econ = entity.tile.get_system("economy")
                if not econ:
                    return bh.Status.FAILURE
                mem = entity.get("memory")
                mem.record_econ(econ)
                # use memory trend detection
                trend = mem.detect_trend("supplies")
                # crisis if immediate supplies below threshold OR trend declining
                if econ["supplies"] < econ["population"] * 0.6 or trend == "declining":
                    return bh.Status.SUCCESS
                return bh.Status.FAILURE

        class HandleSupplyAction(bh.Node):
            def tick(self):
                action = entity.get("action")
                dip = entity.get("diplomacy")
                mem = entity.get("memory")
                econ = entity.tile.get_system("economy")

                # If we have a local partner that recently asked, try to trade/ask
                # If supplies extremely low, request aid; else try small internal increase

                # if econ["supplies"] < 2:
                #     action.trigger_event("trade_mission")

                # if econ["supplies"] < econ["population"] * 0.4:
                if econ["supplies"] < 2:
                    LogEntityEvent(entity, "DIPLOMACY", "Emergency shortage triggered.")

                    # emergency: request aid from nearest partner
                    if dip:
                        dip.request_aid(entity.tile.index.world if getattr(entity.tile, "index", None) else None,
                                        reason="emergency_shortage")
                    # if action:
                    #     action.increase_supplies(amount=5)
                    return bh.Status.SUCCESS

                # If trend declining, attempt trade mission (uses event system)
                trend = mem.detect_trend("supplies")
                if trend == "declining":
                    if action:
                        action.trigger_event("trade_mission")
                    return bh.Status.SUCCESS

                # fallback small harvest push
                if action:
                    action.trigger_event("do_nothing")
                    # action.add_supplies(1)
                return bh.Status.SUCCESS

        class CheckProsperity(bh.Node):
            def tick(self):
                econ = entity.tile.get_system("economy")
                if not econ:
                    return bh.Status.FAILURE
                if econ.get("wealth", 0) > 110:
                    return bh.Status.SUCCESS
                return bh.Status.FAILURE

        class CelebrateAction(bh.Node):
            def tick(self):
                # boost pride & trigger festival
                emo = entity.get("emotion")
                action = entity.get("action")
                if emo:
                    emo.apply_impulse(0.01, 0, 0)
                if action:
                    action.trigger_event("do_nothing")
                    # action.trigger_event("festival")
                return bh.Status.SUCCESS

        class Idle(bh.Node):
            def tick(self):
                # maintenance: read memory, maybe adjust sub-commodities slowly
                econ = entity.tile.get_system("economy")
                subs = econ.get("sub_commodities", {}) if econ else {}
                # small passive adjustment
                for k in subs:
                    subs[k] = max(0.0, subs[k] * 0.999)
                return bh.Status.SUCCESS

        class CheckAndExecuteRaid(bh.Node):
            def tick(self):
                # 1. Check Self-Tendency: Only act if raid drive exceed threshold
                tend = entity.get("tendency")
                econ = entity.tile.get_system("economy")

                # --- 1.1 Compute raid inclination ---
                raid_drive = (
                        tend.get("aggression") * 0.4 +
                        tend.get("risk") * 0.3 +
                        (-tend.get("social")) * 0.2 +
                        (-tend.get("authority")) * 0.1
                )

                # --- 1.2 Contextual pressure modifiers ---
                if econ and econ.get("supplies", 0) < econ.get("population", 1) * 0.6:
                   raid_drive += 0.2  # desperation boost

                LogEntityEvent(
                    entity,
                    "AI:RAID DECISION",
                    f"drive={raid_drive:.2f} "
                    f"(agg={tend.get('aggression'):.2f}, "
                    f"risk={tend.get('risk'):.2f}, "
                    f"social={tend.get('social'):.2f}, "
                    f"auth={tend.get('authority'):.2f})"
                )

                # --- 1.3 Threshold check (soft) ---
                if raid_drive < 0.4:
                   return bh.Status.FAILURE

                LogEntityEvent(
                    entity.tile,
                    "AI",
                    f"Triggering raid action.",
                )

                # 2. Find Target: Look for nearby vulnerable settlements
                target_tile = None

                # Check neighbors within radius=5 (from PerceptionComponent init)
                for n_tile in entity.get("perception").blackboard.get("neighbors", []):
                    econ = n_tile.get_system("economy")
                    if not econ or n_tile is entity.tile:
                        continue

                    # Vulnerable Target: Wealthy AND Struggling
                    if n_tile.has_tag("wealthy") and n_tile.has_tag("struggling"):
                        target_tile = n_tile
                        break

                if target_tile:
                    LogEntityEvent(
                        entity.tile,
                        "AI",
                        f"Found valid raid target.",
                        target_entity=target_tile

                    )

                    # 3. Trigger Raid Payload
                    action = entity.get("action")
                    action.trigger_event("raid")  # Use "raid" which sends the payload

                    # 4. Add Flavor Tag to Self
                    entity.tile.add_tag("opportunistic_raid")

                    # Store destination for payload system if needed (TriggerEventFromLibrary handles this now)
                    entity.tile.temp_dest = target_tile

                    LogEntityEvent(entity, "[AI] RAIDS", "Targeting " + target_tile.pos + "(Vulnerable).")
                    return bh.Status.SUCCESS

                return bh.Status.FAILURE

        class CheckAndExecuteAid(bh.Node):
            def tick(self):
                # 1. Uses unified personality traits
                pers = entity.get("personality")
                if pers.get("agreeableness") < 0.6:  # Replaces 'cooperative'
                    return bh.Status.FAILURE

                # 2. Check Self-Resources: Must have a surplus to give aid
                econ = entity.tile.get_system("economy")
                # if econ.get("supplies", 0) < econ.get("population", 1) * 1.5:
                if econ.get("supplies", 0) < 20:
                    return bh.Status.FAILURE

                # 3. Find Target: Check Memory for aid requests
                mem = entity.get("memory")
                aid_request_key = next((k for k in mem.short if k.startswith("aid_request_from_")), None)

                if aid_request_key:
                    # Target found in memory (via DiplomacyComponent's broadcast)
                    v = mem.recall(aid_request_key)
                    coords = v["from"]

                    if coords:
                        # Find the tile (assumes index is available)
                        rx, ry = coords
                        world = entity.tile.index.world
                        target_tile = world[ry][rx]

                        # 4. Trigger Aid Payload (via DiplomacyComponent)
                        dip = entity.get("diplomacy")
                        dip.offer_aid(world, target_tile, amount_supplies=3)

                        # 5. Add Flavor Tag to Self
                        entity.tile.add_tag("diplomatic_support")

                        LogEntityEvent(entity, "[AI] AID", "Offering aid to " + target_tile.pos + "(Crisis).")
                        # Clear memory entry after action
                        del mem.short[aid_request_key]
                        return bh.Status.SUCCESS

                return bh.Status.FAILURE

        class CheckAmbitiousState(bh.Node):
            def tick(self):
                econ = entity.tile.get_system("economy")
                pers = entity.get("personality")
                if not econ:
                    return bh.Status.FAILURE

                # Prosperity Check: Only act when healthy (Supplies are NOT in crisis)
                is_stable = econ["supplies"] > econ["population"] * 0.8

                # Dominance Check: Is the trait score above threshold?
                is_dominant = pers.get("dominance") > 0.6

                # Wealth Check: Only invest ambition if there's wealth to risk
                is_wealthy = econ.get("wealth", 0) > 150

                if is_stable and is_dominant and is_wealthy:
                    return bh.Status.SUCCESS
                return bh.Status.FAILURE

        # 📌 NEW NODE 2: Execute ambitious action (Raid or Hoard)
        class HandleAmbitiousAction(bh.Node):
            def tick(self):
                action = entity.get("action")
                pers = entity.get("personality")

                # If Aggressive, ambition manifests as expansion/raid
                if pers.get("novelty") > 0.7 and pers.get("agreeableness") < 0.3:
                    # Trigger opportunistic raid event (seeks vulnerable target)
                    action.trigger_event("raid")
                    entity.tile.add_tag("seeking_dominance")

                    LogEntityEvent(entity, "[AI] AMBITION", "Triggered RAID for expansion.")

                # If Cautious/Greedy, ambition manifests as hoarding wealth
                else:
                    # Schedule a financial event to grow wealth long-term
                    from tile_events import ScheduleTileEvent
                    ScheduleTileEvent(entity.tile, "market_boom",
                                      start_tick=entity.tile.get_system("economy").get("id", 0) % 5 + 1)
                    entity.tile.add_tag("hoarding_wealth")
                    LogEntityEvent(entity, "[AI] AMBITION", "Triggered Market Boom for hoarding.")

                return bh.Status.SUCCESS

        # --- NEW BORDER EXPANSION / TILE CLAIMING LOGIC (Priority 7) ---

        CLAIM_COST = 5.0  # Power projection cost to establish a claim
        CLAIM_SUPPLIES_THRESHOLD = 0.8  # Must have supplies > 80% of population
        CLAIM_RANGE = 3  # Search radius for unclaimed tiles

        class CheckCanClaimTile(bh.Node):
            def tick(self):
                econ = entity.tile.get_system("economy")

                if not econ:
                    return bh.Status.FAILURE

                # 1. Check Resources & Stability
                power_proj = econ.get("power_projection", 0)
                is_stable = econ["supplies"] > econ["population"] * CLAIM_SUPPLIES_THRESHOLD

                if power_proj < CLAIM_COST or not is_stable:
                    return bh.Status.FAILURE

                # 2. Find Target: Look for nearby unclaimed tiles
                target_tile = None

                # Use a specific scan for tiles within the claim radius
                world = entity.tile.index.world if getattr(entity.tile, "index", None) else None
                if not world:
                    return bh.Status.FAILURE

                # Note: This relies on GetTilesWithinRadius being available
                for n_tile in GetTilesWithinRadius(world, entity.tile.x, entity.tile.y, radius=CLAIM_RANGE):
                    # Check if tile is valid (not self, not water/mountain)
                    if n_tile is entity.tile or n_tile.terrain in ["water", "mountain"]:
                        continue

                    claim_system = n_tile.get_system("claim")
                    if claim_system:
                        # Skip if already claimed
                        continue

                    # Target found! (Simple rule: claim the first available neutral tile)
                    target_tile = n_tile
                    break

                if target_tile:
                    # Store the target for the action node
                    entity.tile.temp_claim_target = target_tile
                    return bh.Status.SUCCESS

                return bh.Status.FAILURE

        class ExecuteClaimAction(bh.Node):
            def tick(self):
                econ = entity.tile.get_system("economy")
                target_tile = getattr(entity.tile, "temp_claim_target", None)

                if not target_tile:
                    return bh.Status.FAILURE

                # 1. Spend Power Projection
                econ["power_projection"] = econ.get("power_projection", 0) - CLAIM_COST
                LogEntityEvent(entity, "AI:EXPANSION", f"Spent {CLAIM_COST} PP to claim {target_tile.pos}.")

                # 2. Establish Claim System on Target Tile (Sub-settlement data)
                target_tile.attach_system("claim", {
                    "owner_id": entity.id,
                    "power_projection": 1.0,  # Claim strength (can be increased later)
                    "is_sub_settlement": True,
                    "supplies_bonus": 0.5,  # Small base supplies bonus
                })

                # 3. Add Flavor Tag
                entity.tile.add_tag("territorial_expansion")

                # 4. Cleanup temp data
                if hasattr(entity.tile, "temp_claim_target"):
                    del entity.tile.temp_claim_target

                return bh.Status.SUCCESS

        # Compose BT
        root = bh.Selector([
            bh.Sequence([CheckThreat(), DefendAction()]),  # Priority 1: DEFEND
            CheckAndExecuteRaid(),  # Priority 2: RAID (Opportunistic)
            CheckAndExecuteAid(),  # Priority 3: AID (Diplomatic)
            bh.Sequence([CheckSupplyCrisis(), HandleSupplyAction()]),  # Priority 4: SELF-HELP (if raid/aid failed)
            bh.Sequence([CheckProsperity(), CelebrateAction()]), # Priority 5 : Handle prosperity
            bh.Sequence([CheckAmbitiousState(), HandleAmbitiousAction()]), # Priority 6: Handle Ambition
            bh.Sequence([CheckCanClaimTile(), ExecuteClaimAction()]),  # Priority 7: CLAIM TILE
            Idle()
        ])
        # attach onto AI component (entity.get("ai").behavior_tree)
        ai_comp = entity.get("ai")
        if ai_comp:
            ai_comp.behavior_tree = root
        self._bt_built = True

    def update(self, world):
        """
        High level update:
          - power projection initialization & claim maintenance
          - supplies bonus calculation from sub-settlements/claims
          - perception & memory recording
          - emotions updated automatically via emotion component
          - ensure BT exists and let AIComponent.tick() run it
        """
        tile = self.entity.tile
        econ = tile.get_system("economy")
        entity = self.entity
        if not econ:
            return

        # NEW: Initialize Power Projection if missing (for demo/stability)
        if "power_projection" not in econ:
            econ["power_projection"] = 10.0  # Starting PP

        # ensure subcomponents exist
        mem = self.entity.get("memory")
        emo = self.entity.get("emotion")
        dip = self.entity.get("diplomacy")
        action = self.entity.get("action")
        ai = self.entity.get("ai")
        perc = self.entity.get("perception")
        pers = self.entity.get("personality")
        rel = self.entity.get("relationship")

        # -----------------------------------------------------------------
        # NEW: Claim Maintenance and Supplies Bonus (High-Priority Update)
        # -----------------------------------------------------------------

        CLAIM_MAINTENANCE_COST_PER_TICK = 0.05
        MAINTENANCE_RADIUS = 5
        owned_claims_bonus = 0.0

        try:
            # Check tiles within radius (assuming claims are nearby for local calculation)
            nearby_tiles = GetTilesWithinRadius(entity.tile.index.world, tile.x, tile.y, radius=MAINTENANCE_RADIUS)

            for n_tile in nearby_tiles:
                claim = n_tile.get_system("claim")

                if claim and claim.get("owner_id") == entity.id:
                    # 1. Maintenance Cost (Drain Power Projection for upkeep)
                    econ["power_projection"] = econ.get("power_projection", 0) - CLAIM_MAINTENANCE_COST_PER_TICK

                    # 2. Check for loss of claim
                    if econ.get("power_projection", 0) <= 0:
                        n_tile.systems.pop("claim", None)  # Remove the claim system
                        LogEntityEvent(entity, "[AI] BORDER", f"Lost claim on {n_tile.pos} (No PP).")
                    else:
                        # 3. Apply Supplies Bonus (only if claim is maintained)
                        bonus = claim.get("supplies_bonus", 0.0)
                        owned_claims_bonus += bonus

                        # Add tag to indicate it's an active sub-settlement
                        n_tile.add_tag("sub_settlement")

        except Exception:
            # Safely fail if indexing or world is not fully initialized
            pass

        # Apply the total bonus to the owner's supplies
        if owned_claims_bonus > 0.0:
            econ["supplies"] = econ.get("supplies", 0) + owned_claims_bonus
            # LogEntityEvent(entity, "[AI] BORDER", f"Gained {owned_claims_bonus:.2f} supplies from claims.")

        # -----------------------------------------------------------------

        # 1) record economics into memory for trend detection
        if mem:
            mem.record_econ(econ)

        # 2) react to persistent tags (weather already handled earlier)
        weather = tile.get_system("weather")
        if weather:
            w_state = weather.get("state")
            if w_state == "drought":
                if emo:
                    emo.mod("fear", 0.08)

        # --- STEP 0: Retrieve Perception Variables ---
        # sv: sensory intensity [0,1], i_raw: perceived intent [-1,1], u: uncertainty [0,1]
        sv = perc.blackboard.get("sv", 0.1)
        i_raw = perc.blackboard.get("i_raw", 0.0)
        u = perc.blackboard.get("u", 0.1)

        # Attribution modifier (A_mod): biased by personality traits
        # High agreeableness reduces negative attribution
        a_mod = (pers.get("agreeableness") - 0.5) * 0.2

        # --- STEP 1: Compute Valence (V) ---
        # Formula: V = (1 - u)(I_raw + A_mod) + alpha * Rv
        alpha = 0.2  # weighting coefficient (0.1-0.3)

        neighbors = perc.blackboard.get("neighbors", [])
        total_v, total_a, total_s = 0, 0, 0
        for n in neighbors:
            if not n.entities: continue
            target_id = n.entities[0].id
            rv = rel.get_rv(target_id) if rel else 0.0

            # Formal Valence calculation
            v_event = (1 - u) * (i_raw + a_mod) + (alpha * rv)

            # --- STEP 2: Compute Arousal (A) ---
            # Formula: A = SV(1 + u) + beta * Ra
            # (Simplifying Ra as internal tension or 0 for now)
            a_event = sv * (1 + u)

            # --- STEP 3: Compute Sociality (S) ---
            # Formula: S = V + I_raw + dominance + Rs
            rs = rel.get_rs(target_id) if rel else 0.0
            dom_weight = 0.9  # Matches the Case Study logic
            s_event = (0.6 * v_event) + (0.3 * i_raw) + (dom_weight * pers.get("dominance")) + rs

            # --- STEP 4: Apply Impulses ---
            # Using a scalar to prevent instant maxing of vectors
            scalar = 0.2
            total_v += v_event * scalar
            total_a += a_event * scalar
            total_s += s_event * scalar

            # --- STEP 5: Update Relationship Memory EMA ---
            # R'v = 0.9Rv + 0.1V | R's = 0.9Rs + 0.1S
            if rel:
                scalar = 0.5
                rel.update_relationship(target_id, v_event, s_event * scalar)

        emo.apply_impulse(total_v, total_a, total_s)

        # --- STEP 6: Logging Interpretation ---
        label = emo.get_current_label()
        LogEntityEvent(entity, "AI:EMOTION VAS", f"State: {label} (V:{emo.v:.2f}, A:{emo.a:.2f}, S:{emo.s:.2f})")

        # 3) lazy-build behaviour tree (only once per entity)
        if not self._bt_built:
            self._build_behavior_tree()

        # 4) Let AI component tick the BT (AIComponent.update handles tick)
        if ai:
            ai.update(world)

    def oldUpdate(self, world):
        """
        Baby steps 1–6:
          1) Daily pulse -> tag the settlement condition
          2) Push simple goals (increase_supplies)
          3) Influence sub-commodities (basic economy shaping)
          4) Weather reaction
          5) Neighbor awareness
          6) Spawn micro event
        """
        tile = self.entity.tile
        econ = tile.get_system("economy")
        if not econ:
            return

        supplies = econ["supplies"]
        pop = econ["population"]

        # Components
        goals = self.entity.get("goals")
        action = self.entity.get("action")
        pop_weight = 0.5

        # ---------------------------------------------------------
        # BABY STEP 1 — "Daily Pulse" for Settlement Health
        # ---------------------------------------------------------

        # hunger condition
        if supplies < pop * pop_weight:
            tile.add_tag("hungry")
            tile.remove_tag("food_secure") if tile.has_tag("food_secure") else None
        else:
            tile.add_tag("food_secure")
            tile.remove_tag("hungry") if tile.has_tag("hungry") else None

        # wealth condition
        if econ["wealth"] < 80:
            tile.add_tag("poor")
            if tile.has_tag("wealthy"):
                tile.remove_tag("wealthy")
        elif econ["wealth"] > 120:
            tile.add_tag("wealthy")
            if tile.has_tag("poor"):
                tile.remove_tag("poor")

        # ---------------------------------------------------------
        # BABY STEP 2 — Simple Goal: Increase Supplies
        # ---------------------------------------------------------

        if supplies < pop * pop_weight:
            goals.push("increase_supplies")

        # ---------------------------------------------------------
        # BABY STEP 3 — Influence Sub-commodities
        # ---------------------------------------------------------
        subs = econ.get("sub_commodities", {})

        # If starving → grow food faster
        if tile.has_tag("hungry"):
            for name in subs:
                if "grain" in name or "meat" in name or "fish" in name:
                    subs[name] += 0.3  # small growth boost

        # If wealthy → upgrade luxuries (narrative flourish)
        if tile.has_tag("wealthy"):
            for name in subs:
                if "spices" in name or "fruit" in name:
                    subs[name] += 0.1

        # ================================================================
        # BABY STEP 4 — Weather Reaction
        # ================================================================
        weather = tile.get_system("weather")

        if weather:
            w_state = weather.get("state")
            # w_state = "drought"

            if w_state == "drought":
                tile.add_tag("water_crisis")
                # drought increases food consumption pressure
                goals.push("increase_supplies")

            elif w_state == "storm":
                tile.add_tag("storm_damage")

            elif w_state == "rain":
                # healing effect
                if tile.has_tag("water_crisis"):
                    tile.remove_tag("water_crisis")

        # ================================================================
        # BABY STEP 5 — Neighbor Awareness
        # ================================================================
        # detect nearby settlements and threats
        neighbors = GetTilesWithinRadius(world, tile.x, tile.y, radius=5)
        nearby_bandits = False
        nearby_struggling = False
        nearby_prosperous = False

        for n in neighbors:
            if n is tile:
                continue
            if n.has_tag("bandit_settlement"):
                nearby_bandits = True
            if n.has_tag("struggling") or n.has_tag("hungry"):
                nearby_struggling = True
            if n.has_tag("wealthy") or n.has_tag("trade_hub"):
                nearby_prosperous = True

        # Social interpretation
        if nearby_bandits:
            tile.add_tag("fearful")
            goals.push("increase_supplies")  # stockpiling behavior

        if nearby_struggling and not nearby_bandits:
            tile.add_tag("empathetic")  # possible future trade or aid
        else:
            if tile.has_tag("empathetic"):
                tile.remove_tag("empathetic")

        # ================================================================
        # BABY STEP 6 — Micro-Events
        # ================================================================
        # using the ActionComponent to trigger tile events

        # 6a: food short → launch a trade mission
        if tile.has_tag("hungry") and weather and weather.get("state") != "storm":
            action.trigger_event("trade_mission")

        # 6b: prosperity → festival
        if tile.has_tag("wealthy"):
            action.trigger_event("do_nothing")
            # action.trigger_event("festival")

        # 6c: bandits near → raid risk
        if nearby_bandits and not tile.has_tag("storm_damage"):
            action.trigger_event("raid")

        # =====================================================
        # Execute simple goals
        # =====================================================
        goal = goals.pop()
        if goal == "increase_supplies":
            self.entity.get("action").increase_supplies()
