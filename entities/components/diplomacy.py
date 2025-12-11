# entities/components/diplomacy.py
from ..component import Component
from world_utils import GetNearestTileWithSystem, GetActiveTiles, LogEntityEvent
import world_index_store

class DiplomacyComponent(Component):
    def __init__(self):
        super().__init__("diplomacy")
        # simple relation store: {settlement_id: score}
        self.relations = {}

    def get_nearest_partner(self, world, radius=20):
        # uses world index
        tile = self.entity.tile
        widx = getattr(world_index_store, "world_index", None)
        if widx:
            # find nearest economy tile excluding self
            candidates = [t for t in widx.with_system("economy") if t != tile]
            if not candidates:
                return None
            best = min(candidates, key=lambda t: (t.x - tile.x)**2 + (t.y - tile.y)**2)
            return best
        # fallback: brute search
        return GetNearestTileWithSystem(world, tile.x, tile.y, "economy", max_radius=radius)

    def request_aid(self, world, reason="supply_shortage"):
        """
        Ask nearest partner for help: apply a tag to self and notify partner via memory.
        This is intentionally simple: partner AI can detect 'aid_requested' tags in neighbors.
        """
        partner = self.get_nearest_partner(world)

        if not partner:
            return False

        LogEntityEvent(
            self.entity,
            "DIPLOMACY",
            f"Found nearest partner tile. Checking for aid request broadcast.",
            target_entity=partner
        )

        # mark self asking for aid
        if not self.entity.tile.has_tag("aid_requested"):
            action = self.entity.get("action")
            action.trigger_event("request_aid")

            # Broadcast help to all settlement
            for otherSettlement in GetActiveTiles(world, "economy"):

                if (otherSettlement.x, otherSettlement.y) == (self.entity.tile.x, self.entity.tile.y):
                    # it current tile, so skip it
                    continue

                LogEntityEvent(
                    self.entity,
                    "DIPLOMACY",
                    f"Broadcast help to other settlement.",
                    target_entity=otherSettlement
                )

                for ent in otherSettlement.entities:
                    d = ent.get("diplomacy")

                    # Directly inject it on short memory of other settlement
                    mem = ent.get("memory")
                    if mem:
                        mem.remember(f"aid_request_from_{self.entity.id}", {
                            "from": (self.entity.tile.x, self.entity.tile.y),
                            "reason": reason
                        }, long_term=False)

                        LogEntityEvent(
                            self.entity,
                            "DIPLOMACY",
                            f"Checking memory if there are aid requests. {mem.short}",
                            target_entity=partner
                        )
            return True

        # notify partner by writing into its tile memory (if present)
        # partner may have entities -> find diplomacy or memory component

        # for ent in partner.entities:
        #     d = ent.get("diplomacy")
        #     mem = ent.get("memory")
        #     if mem:
        #         mem.remember(f"aid_request_from_{self.entity.id}", {
        #             "from": (self.entity.tile.x, self.entity.tile.y),
        #             "reason": reason
        #         }, long_term=False)
        # return True

    def offer_aid(self, world, target_tile, amount_supplies=5):

        LogEntityEvent(
            self.entity,
            "DIPLOMACY",
            f"Sending aid to other settlement.",
            target_entity=target_tile
        )
        # Use new payload system to handle supplies sharing and relationship update
        # Inject temporary destination tile on self tile, so payload event can be handled by TriggerEventFromLibrary
        self.entity.tile.temp_dest = target_tile
        action = self.entity.get("action")
        action.trigger_event("send_aid")

        # # simple transfer: increase supplies at target_tile and reduce own econ slightly
        # source_econ = self.entity.tile.get_system("economy")
        # target_econ = target_tile.get_system("economy")
        # if not source_econ or not target_econ:
        #     return False
        #
        # give = min(amount_supplies, max(0, source_econ.get("supplies", 0) * 0.2))
        # source_econ["supplies"] = max(0, source_econ.get("supplies", 0) - give)
        # target_econ["supplies"] = target_econ.get("supplies", 0) + give
        # # tag both for narrative hooks
        # self.entity.tile.add_tag("offered_aid")
        # target_tile.add_tag("received_aid")
        return True

    def update_relations(self, target_id, delta):
        self.relations[target_id] = self.relations.get(target_id, 0.0) + delta

    def update(self, world):
        # nothing here — diplomacy is invoked by AI logic
        pass
