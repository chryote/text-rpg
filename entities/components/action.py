# entities/components/action.py

from ..component import Component
from tile_events import TriggerEventFromLibrary

class ActionComponent(Component):
    def __init__(self):
        super().__init__("action")

    def do(self, action, *args, **kwargs):
        fn = getattr(self, action, None)
        if fn:
            return fn(*args, **kwargs)

    def increase_supplies(self, amount=2):
        """Used by Baby Step 2 — basic self-recovery behavior."""
        econ = self.entity.tile.get_system("economy")
        if econ:
            econ["supplies"] += amount

    # (existing actions remain)
    def add_supplies(self, amount):
        econ = self.entity.tile.get_system("economy")
        if econ:
            econ["supplies"] += amount

    def add_wealth(self, amount):
        econ = self.entity.tile.get_system("economy")
        if econ:
            econ["wealth"] += amount

    def add_tag(self, tag):
        self.entity.tile.add_tag(tag)

    def trigger_event(self, name):
        TriggerEventFromLibrary(self.entity.tile, name)
