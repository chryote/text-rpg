# entities/components/emotion.py
from ..component import Component

class EmotionComponent(Component):
    def __init__(self, fear=0.1, trust=0.5, pride=0.5):
        super().__init__("emotion")
        # values 0..1
        self.fear = fear
        self.trust = trust
        self.pride = pride

    def mod(self, name, delta):
        if name == "fear":
            self.fear = max(0.0, min(1.0, self.fear + delta))
        elif name == "trust":
            self.trust = max(0.0, min(1.0, self.trust + delta))
        elif name == "pride":
            self.pride = max(0.0, min(1.0, self.pride + delta))

    def update(self, world):
        # slow decay towards baseline (0.5) to avoid permanent extremes
        def relax(v):
            return v + (0.5 - v) * 0.02
        self.fear = relax(self.fear)
        self.trust = relax(self.trust)
        self.pride = relax(self.pride)
