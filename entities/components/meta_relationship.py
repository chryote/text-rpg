# entities/components/meta_relationship.py

from ..component import Component


class MetaRelationshipComponent(Component):
    """
    Stores relationship memory toward other entities using the VAS EMA model.
    Each relationship consists of:
    - Rv (Valence): Long-term pleasantness/trust [-1.0 to 1.0]
    - Rs (Sociality): Long-term approach/avoidance tendency [-1.0 to 1.0]
    """

    def __init__(self):
        super().__init__("meta_relationship")
        # key: entity_id -> {'rv': float, 'rs': float}
        self.table = {}

    def initialize(self, self_entity, all_entities):
        """Initializes baseline relationships based on settlement types."""
        econ = self_entity.tile.get_system("economy")
        my_types = set(econ.get("settlement_type", []))

        for other in all_entities:
            if other.id == self_entity.id:
                continue

            other_econ = other.tile.get_system("economy")
            other_types = set(other_econ.get("settlement_type", []))

            shared = my_types.intersection(other_types)
            # Map shared interests to a starting positive valence [0.0 to 1.0]
            base_rv = min(1.0, len(shared) * 0.1)

            self.table[other.id] = {
                "rv": base_rv,
                "rs": 0.0  # Sociality starts neutral
            }

    def update_relationship(self, other_id, current_v, current_s):
        """
        Updates memory using the formal Exponential Moving Average formulas:
        Rv' = 0.9 * Rv + 0.1 * V
        Rs' = 0.9 * Rs + 0.1 * S
        """
        rel = self.table.get(other_id, {"rv": 0.0, "rs": 0.0})

        rel["rv"] = (0.9 * rel["rv"]) + (0.1 * current_v)
        rel["rs"] = (0.9 * rel["rs"]) + (0.1 * current_s)

        # Clamp to ensure numerical stability within [-1, 1]
        rel["rv"] = max(-1.0, min(1.0, rel["rv"]))
        rel["rs"] = max(-1.0, min(1.0, rel["rs"]))

        self.table[other_id] = rel

    def get_rv(self, other_id):
        """Returns the long-term relationship valence baseline."""
        return self.table.get(other_id, {"rv": 0.0})["rv"]

    def get_rs(self, other_id):
        """Returns the long-term sociality memory."""
        return self.table.get(other_id, {"rs": 0.0})["rs"]

    def to_json(self):
        return self.table