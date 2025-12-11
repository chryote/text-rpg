# entities/components/physical.py

from ..component import Component
from world_utils import LogEntityEvent
import json

class PhysicalComponent(Component):
    def __init__(self):
        super().__init__("physical")
        self.path = []
        self.speed = 1

    def update(self, world):
        if not self.path:
            return

        # Payload movement
        tile = self.path.pop(0)

        # Remove from old tile payloads
        prev_tile = getattr(self.entity, "tile", None)
        if prev_tile and hasattr(prev_tile, "payloads"):
            if self.entity in prev_tile.payloads:
                prev_tile.payloads.remove(self.entity)

        # Move entity
        self.entity.tile = tile

        # Add to new tile payloads list
        if not hasattr(tile, "payloads"):
            tile.payloads = []
        tile.payloads.append(self.entity)

        # PAYLOAD ARRIVAL CHECK
        payload_comp = self.entity.components.get("payload")
        if payload_comp:
            # Flavor trail
            try:
                LogEntityEvent(
                    tile,
                    "PAYLOAD",
                    f"Payload arrived on: ({tile.x}, {tile.y}) with destination: {payload_comp.destination}. Payload content: {payload_comp.payload_data}",
                )
                # tile.add_tag("caravan_was_here")
            except:
                pass

            # Destination check
            if (tile.x, tile.y) == payload_comp.destination:
                LogEntityEvent(
                    tile,
                    "PAYLOAD",
                    f"Payload arrived on final destination {payload_comp.destination}",
                )
                payload_comp.on_arrival(tile)
                self.entity.mark_for_removal = True

