# entities/components/personality.py

from ..component import Component

class PersonalityComponent(Component):
    def __init__(self, traits=None):
        super().__init__("personality")
        self.traits = traits or {
            "cautious": 0.5,
            "greedy": 0.5,
            "aggressive": 0.5,
            "cooperative": 0.5,
        }

    def get(self, trait):
        return self.traits.get(trait, 0.5)
