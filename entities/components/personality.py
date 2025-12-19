# entities/components/personality.py

from ..component import Component

class PersonalityComponent(Component):
    """
    Stores stable personality traits that bias emotional interpretation
    and responses according to the VAS formal model.
    """
    def __init__(self, traits=None):
        super().__init__("personality")
        # Default traits aligned with VAS Model Section 3 (docs/VAS.pdf)
        self.traits = traits or {
            "dominance": 0.5,           # Primary driver for Sociality (S)
            "agreeableness": 0.5,       # Influences attribution and relationship growth
            "anxiety_sensitivity": 0.5, # Biases Arousal (A) response to uncertainty
            "novelty_seek": 0.5,        # Affects response to uncertainty (u)
            "self_worth": 0.5           # Influences Valence (V) and attribution
        }

    def get(self, trait):
        """Returns the value of a specific trait, defaulting to neutral (0.5)."""
        return self.traits.get(trait, 0.5)

    def to_json(self):
        return dict(self.traits)