# entities/payload_entity.py

from .entity import Entity
from .components.physical import PhysicalComponent
from .components.action import ActionComponent
from world_utils import LogEntityEvent

class PayloadComponent:
    def __init__(self, source_tile, dest_tile, routes, payload_data, payload_power, sender_entity, entity):
        self.name = "payload"
        self.source = (source_tile.x, source_tile.y)
        self.destination = (dest_tile.x, dest_tile.y)
        self.routes = routes or []
        self.payload_data = payload_data or {}
        self.payload_power = float(payload_power)
        self.sender_id = sender_entity.id if sender_entity else None
        self.sender_entity = sender_entity
        self.delivered = False
        self.entity = entity

    def update(self, world):
        # Nothing to do each tick — arrival handled in PhysicalComponent
        pass

    def on_arrival(self, tile):
        """Apply economy effects + relationship effects."""
        if self.delivered:
            return
        self.delivered = True

        # --- Economy Integration ---
        agent = getattr(tile, "agent", None)
        if agent:
            if "supplies" in self.payload_data:
                LogEntityEvent(
                    tile,
                    "PAYLOAD",
                    f"Updating supplies by {self.payload_data['supplies']}",
                )
                agent.add_supplies(self.payload_data["supplies"] * self.payload_power, 1)

            if "wealth" in self.payload_data:
                agent.add_wealth(self.payload_data["wealth"] * self.payload_power, 1)

            if "sub_commodities" in self.payload_data:
                LogEntityEvent(
                    tile,
                    "PAYLOAD",
                    f"Inspecting sub commodities from payload data: {self.payload_data['sub_commodities']}",
                )
                for cname, amt in self.payload_data["sub_commodities"].items():
                    LogEntityEvent(
                        tile,
                        "PAYLOAD",
                        f"Adding sub commodity {amt} {cname} multiplied by {self.payload_power} (payload power)",
                    )
                    agent.add_sub_commodity(amt * self.payload_power, cname)

        # --- Relationship Integration ---
        for ent in list(tile.entities):
            rel = ent.components.get("relationship")
            LogEntityEvent(
                tile,
                "PAYLOAD",
                f"Inspecting relationship table {rel.to_json()}",
            )
            if rel and self.sender_id:
                delta = self.payload_data.get("relationship_mod", 0)

                LogEntityEvent(
                    tile,
                    "PAYLOAD",
                    f"Change perceived relationship of {self.sender_id} to {int(delta * self.payload_power)}",
                )

                rel.modify(self.sender_id, int(delta * self.payload_power))

        # --- Tags / Flavor ---
        # tile.add_tag(f"payload_arrived_{self.payload_data.get('type','generic')}")
        # tile.add_tag(f"payload_from_{self.source[0]}_{self.source[1]}")

def CreatePayloadEntity(world, source_tile, dest_tile, payload_data, routes, sender_entity, power=1.0):
    """Factory for creating payload entities."""

    LogEntityEvent(
        source_tile,
        "PAYLOAD",
        f"Create and observe payload.",
        target_entity=dest_tile
    )

    eid = f"payload_{source_tile.x}_{source_tile.y}_{dest_tile.x}_{dest_tile.y}"

    LogEntityEvent(
        source_tile,
        "PAYLOAD",
        f"Payload generated with entity_id (eid) {eid}.",
        target_entity=dest_tile
    )
    e = Entity(eid, "payload", source_tile)

    # Movement
    phys = PhysicalComponent()
    phys.path = list(routes) if routes else []
    e.add_component(phys)

    # Existing action component
    e.add_component(ActionComponent())

    # Payload component
    payload_comp = PayloadComponent(
        source_tile, dest_tile, routes, payload_data, power, sender_entity, e
    )
    e.add_component(payload_comp)

    return e
