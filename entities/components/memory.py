# entities/components/memory.py
from ..component import Component
from collections import deque

class MemoryComponent(Component):
    def __init__(self, max_len=30):
        super().__init__("memory")
        # short-term ephemeral memory
        self.short = {}
        # long-term entries such as relations or persistent notices
        self.long = {}
        # rolling economy history for trend detection
        self.econ_history = {
            "supplies": deque(maxlen=max_len),
            "wealth": deque(maxlen=max_len),
            "population": deque(maxlen=max_len)
        }
        self.max_len = max_len

    # convenience - snapshot current econ into history
    def record_econ(self, econ):
        if not econ:
            return
        self.econ_history["supplies"].append(float(econ.get("supplies", 0)))
        self.econ_history["wealth"].append(float(econ.get("wealth", 0)))
        self.econ_history["population"].append(int(econ.get("population", 0)))

    def detect_trend(self, key="supplies", lookback=6, thresh_pct=0.05):
        """
        Simple trend detector:
          - Returns "improving" / "declining" / "stable"
          - Compares average of last lookback values to previous lookback values.
        """
        arr = list(self.econ_history.get(key, []))
        n = len(arr)
        if n < lookback * 2:
            return "stable"

        recent = arr[-lookback:]
        prev = arr[-lookback*2:-lookback]

        avg_recent = sum(recent) / len(recent)
        avg_prev = sum(prev) / len(prev) if prev else avg_recent

        if avg_prev == 0:
            return "stable"

        pct = (avg_recent - avg_prev) / max(1.0, avg_prev)

        if pct > thresh_pct:
            return "improving"
        if pct < -thresh_pct:
            return "declining"
        return "stable"

    def remember(self, key, value, long_term=False):
        if long_term:
            self.long[key] = value
        else:
            self.short[key] = value

    def recall(self, key, default=None):
        return self.short.get(key, self.long.get(key, default))

    def update(self, world):
        # by default, short-term memory decays each tick (caller can override)
        self.short.clear()

