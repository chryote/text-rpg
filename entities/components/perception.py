# entities/components/perception.py

from ..component import Component
from world_utils import GetTilesWithinRadius

class PerceptionComponent(Component):
    def __init__(self, radius=3):
        super().__init__("perception")
        self.radius = radius
        self.blackboard = {}

    def update(self, world):
        t = self.entity.tile
        neighbors = GetTilesWithinRadius(world, t.x, t.y, self.radius)

        wsys = t.get_system("weather")
        eco_risk = t.get_system("eco_risk")

        self.blackboard.update({
            "neighbors": neighbors,
            "weather": wsys.get("state") if wsys else None,
            "eco_risk": eco_risk.get("value") if eco_risk else None,
            "tags": list(t.tags)
        })
