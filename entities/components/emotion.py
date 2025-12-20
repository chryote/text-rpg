# entities/components/emotion.py
from ..component import Component
import math

# Reference anchors from test_vas_mapping.py
EMOTION_ANCHORS = {
    "Love/Ecstasy": (1.0, 0.6, 1.0),
    "Excitement/Elation": (0.9, 0.8, -0.5),
    "Anger/Rage": (-0.7, 1.0, 0.7),
    "Fear/Terror": (-0.8, 0.9, -0.9),
    "Distress/Anxiety": (-0.6, 0.7, 0.0),
    "Disgust/Aversion": (-0.5, 0.7, -0.9),
    "Sadness/Grief": (-0.7, 0.3, -0.2),
    "Serenity/Contentment": (0.8, 0.1, 0.5),
    "Calmness/Apathy": (0.0, 0.0, 0.0),
    "Relaxation": (0.3, 0.1, 0.2),
    "Boredom/Dullness": (-0.3, 0.1, -0.3),
    "Interest/Ambivalence": (0.0, 0.4, 0.0),
}


class EmotionComponent(Component):
    def __init__(self, v=0.0, a=0.0, s=0.0, decay_rate=0.02, stacking_factor=0.01):
        super().__init__("emotion")
        # VAS Dimensions: V [-1,1], A [0,1], S [-1,1]
        self.v = v
        self.a = arousal = a
        self.s = s
        self.decay_rate = decay_rate
        # k factor (0.05 - 0.2) as per VAS docs
        self.stacking_factor = stacking_factor

    def apply_impulse(self, dv, da, ds):
        """Applies an emotional shift and clamps values to their physical bounds."""
        k = self.stacking_factor

        # Calculate new values with stacking
        self.v = (self.v + dv) + (k * self.v)
        self.a = (self.a + da) + (k * self.a)
        self.s = (self.s + ds) + (k * self.s)

        # Then apply stacking (growth based on current state)
        # but only if the impulse is pushing in the same direction
        if (dv > 0 and self.v > 0) or (dv < 0 and self.v < 0):
            self.v += self.stacking_factor * self.v

        if (da > 0 and self.a > 0) or (da < 0 and self.a < 0):
            self.a += self.stacking_factor * self.a

        if (ds > 0 and self.s > 0) or (ds < 0 and self.s < 0):
            self.s += self.stacking_factor * self.s

        # Physical bounds clamping
        self.v = max(-1.0, min(1.0, self.v))
        self.a = max(0.0, min(1.0, self.a))
        self.s = max(-1.0, min(1.0, self.s))

    def get_current_label(self):
        """Uses the RBF competition logic to find the dominant emotion label."""
        agent_point = (self.v, self.a, self.s)
        best_label = "Calmness/Apathy"
        max_activation = -1.0
        sigma = 0.35

        for label, anchor in EMOTION_ANCHORS.items():
            # Euclidean distance calculation
            dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(agent_point, anchor)))
            # Gaussian RBF activation
            activation = math.exp(-(dist ** 2) / (2 * sigma ** 2))

            if activation > max_activation:
                max_activation = activation
                best_label = label

        return best_label

    def update(self, world):
        """Natural decay towards the neutral baseline (0,0,0)."""
        self.v *= (1.0 - self.decay_rate)
        self.a *= (1.0 - self.decay_rate)
        self.s *= (1.0 - self.decay_rate)