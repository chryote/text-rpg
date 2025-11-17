# entities/components/relationship.py

from ..component import Component

class RelationshipComponent(Component):
    """
    Stores relationship scores toward other agents.
    Score: -100 (hate) to +100 (love)

    agent.components["relationship"].modify(other.id, +5)
    agent.components["relationship"].modify(other.id, -15)
    agent.components["relationship"].set(other.id, 75)
    score = agent.components["relationship"].get(other.id)
    """
    def __init__(self):
        # key: entity_id -> int
        super().__init__("relationship")
        self.table = {}

    def initialize(self, self_entity, all_entities):
        econ = self_entity.tile.get_system("economy")
        my_types = set(econ["settlement_type"])

        for other in all_entities:
            if other.id == self_entity.id:
                continue

            other_econ = other.tile.get_system("economy")
            other_types = set(other_econ["settlement_type"])

            shared = my_types.intersection(other_types)
            base_score = min(100, len(shared) * 5)

            self.table[other.id] = base_score

    def get(self, other_id):
        """Return relationship score toward another entity."""
        return self.table.get(other_id, 0)

    def set(self, other_id, value):
        """Set relationship score, clamped to [-100, 100]."""
        value = max(-100, min(100, value))
        self.table[other_id] = value

    def modify(self, other_id, delta):
        """Modify relationship score by delta."""
        current = self.get(other_id)
        self.set(other_id, current + delta)

    def to_json(self):
        return dict(self.table)
