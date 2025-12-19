# entities/components/meta_emotion.py
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


class MetaEmotionComponent(Component):
    def __init__(self, v=0.0, a=0.0, s=0.0, decay_rate=0.02):
        super().__init__("meta_emotion")
        # VAS Dimensions: V [-1,1], A [0,1], S [-1,1]
        self.v = v
        self.a = arousal = a
        self.s = s
        self.decay_rate = decay_rate

    def apply_impulse(self, dv, da, ds):
        """Applies an emotional shift and clamps values to their physical bounds."""
        self.v = max(-1.0, min(1.0, self.v + dv))
        self.a = max(0.0, min(1.0, self.a + da))
        self.s = max(-1.0, min(1.0, self.s + ds))

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