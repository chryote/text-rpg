# entities/components/tendency.py

from ..component import Component

# separate tendency and personality through : TENDENCIES → DECISIONS → BEHAVIOR OVER TIME → PERSONALITY
# Tendency Range: -1.0 → +1.0

class TendencyComponent(Component):
    def __init__(self, tendencies=None):
        super().__init__("tendency")
        self.tendencies = tendencies or {
            # Risk Sensitivity (Avoidance ↔ Seeking), How much danger am I willing to tolerate?
            "risk": 0.5,

            # Aggression Threshold (Passive ↔ Confrontational), When do I use force or coercion?
            "aggression": 0.5,

            # Social Orientation (Self ↔ Group), Whose outcome matters most?
            "social": 0.5,

            # Authority Orientation (Independent ↔ Conformist), Do I trust rules and hierarchy?
            "authority": 0.5,

            # Time Horizon (Impulsive ↔ Patient), Now or later?
            "patience": 0.5,

            # Novelty Orientation (Routine ↔ Exploratory), Do I stick to known patterns?
            "novelty": 0.5,
        }

    def get(self, tendency):
        return self.tendencies.get(tendency, 0.5)
