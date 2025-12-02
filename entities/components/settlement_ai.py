# entities/components/settlement_ai.py

from ..component import Component
from world_utils import GetTilesWithinRadius, GetNearestTileWithSystem
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
                tile = entity.tile
                # local neighbor scan
                neigh = GetTilesWithinRadius(entity.tile.index.world, tile.x, tile.y, radius=5) if getattr(entity.tile,
                                                                                                           "index",
                                                                                                           None) else []
                for n in neigh:
                    if n is tile:
                        continue
                    if n.has_tag("bandit_settlement") or n.has_tag("predator_surge"):
                        return bh.Status.SUCCESS
                return bh.Status.FAILURE

        class DefendAction(bh.Node):
            def tick(self):
                # simple defend: raise fear emotion and stockpile supplies
                action = entity.get("action")
                emo = entity.get("emotion")
                mem = entity.get("memory")
                if emo:
                    emo.mod("fear", 0.2)
                if action:
                    action.trigger_event("do_nothing")
                    # action.add_supplies(1)  # small stockpile
                # also set a fearful tag for narrative
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
                    print("[DEBUG:DIPLOMACY] EMERGENCY SHORTAGE TRIGGERED")
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
                    emo.mod("pride", 0.15)
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

        # Compose BT
        root = bh.Selector([
            bh.Sequence([CheckThreat(), DefendAction()]),
            bh.Sequence([CheckSupplyCrisis(), HandleSupplyAction()]),
            bh.Sequence([CheckProsperity(), CelebrateAction()]),
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
          - perception & memory recording (some already in PerceptionComponent)
          - emotions updated automatically via emotion component
          - ensure BT exists and let AIComponent.tick() run it
        """
        tile = self.entity.tile
        econ = tile.get_system("economy")
        if not econ:
            return

        if (tile.x, tile.y) == (8,1):
            print ("[DEBUG:ECONOMY] INSPECTING (8,1) : ", econ["supplies"])

        # ensure subcomponents exist
        mem = self.entity.get("memory")
        emo = self.entity.get("emotion")
        dip = self.entity.get("diplomacy")
        action = self.entity.get("action")
        ai = self.entity.get("ai")

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

        # 3) lazy-build behaviour tree (only once per entity)
        if not self._bt_built:
            self._build_behavior_tree()

        # 4) Let AI component tick the BT (AIComponent.update handles tick)
        if ai:
            ai.update(world)

        # 5) Diplomatic auto-response: if memory has aid_request entries, consider offering small help
        if dip and mem:
            # simple heuristic: if we have high supplies and recently saw aid request, give a little
            for k, v in list(mem.short.items()):
                if k.startswith("aid_request_from_"):
                    # if econ.get("supplies", 0) > econ.get("population", 1) * 1.5:
                    if econ.get("supplies", 0) > 2:
                        print("[DEBUG:DIPLOMACY] CHECKING FOR AID REQUEST", k)
                        # find requester tile coordinates in v and offer aid
                        v = mem.recall(k)
                        coords = v["from"]

                        if coords:
                            rx, ry = coords
                            try:
                                requester_tile = tile.index.world[ry][rx]
                                dip.offer_aid(tile.index.world, requester_tile, amount_supplies=3)
                                # reduce trust? increase trust? we'll nudge relation
                                # dip.update_relations(v.get("from"), 0.1)
                            except Exception:
                                pass
                    # clear processed aid request from memory
                    del mem.short[k]

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
        # 🍼 BABY STEP 1 — "Daily Pulse" for Settlement Health
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
        # 🍼 BABY STEP 2 — Simple Goal: Increase Supplies
        # ---------------------------------------------------------

        if supplies < pop * pop_weight:
            goals.push("increase_supplies")

        # ---------------------------------------------------------
        # 🍼 BABY STEP 3 — Influence Sub-commodities
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
        # 🍼 BABY STEP 4 — Weather Reaction
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
        # 🍼 BABY STEP 5 — Neighbor Awareness
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
        # 🍼 BABY STEP 6 — Micro-Events
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
