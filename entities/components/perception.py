# entities/components/perception.py

from ..component import Component
from world_utils import GetTilesWithinRadius, GetActiveTiles


class PerceptionComponent(Component):
    def __init__(self, radius=3):
        super().__init__("perception")
        self.radius = radius
        # The blackboard now stores VAS-specific interpretation variables
        self.blackboard = {
            "sv": 0.0,  # Sensory Intensity [0, 1]
            "i_raw": 0.0,  # Perceived Intent [-1, 1]
            "u": 0.0,  # Uncertainty [0, 1]
            "neighbors": [],
            "tags": []
        }

    def update(self, world):
        t = self.entity.tile
        neighbors = GetActiveTiles(world, "economy")

        # Reset intensities for the current pulse
        sv = 0.1  # Base ambient intensity
        i_raw = 0.0
        u = 0.1  # Base ambient uncertainty

        # 1. Interpret Weather
        wsys = t.get_system("weather")
        if wsys:
            state = wsys.get("state")
            if state == "storm":
                sv = 0.7  # High sensory impact
                u = 0.5  # Chaos increases uncertainty
            elif state == "drought":
                sv = 0.4
                i_raw = -0.1  # Nature is perceived as slightly "hostile"
                u = 0.2

        # 2. Interpret Social Threats (Neighbors)
        for n in neighbors:
            if n.has_tag("bandit_settlement"):
                sv = max(sv, 0.6)
                i_raw = min(i_raw, -0.7)  # Clear negative intent
                u = max(u, 0.4)  # Threat increases anxiety/uncertainty

            if n.has_tag("predator_surge"):
                sv = max(sv, 0.8)
                i_raw = min(i_raw, -0.5)
                u = max(u, 0.6)

        # 3. Interpret Local Tags
        if t.has_tag("hungry") or t.has_tag("water_crisis"):
            sv = max(sv, 0.5)
            u = max(u, 0.3)

        self.blackboard.update({
            "sv": sv,
            "i_raw": i_raw,
            "u": u,
            "neighbors": neighbors,
            "tags": list(t.tags)
        })