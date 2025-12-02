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
            # TTL = 2 ticks
            self.short[key] = (value, 2)

    def recall(self, key, default=None):
        if key in self.short:
            return self.short[key][0]  # return the value only
        return self.long.get(key, default)
        # return self.short.get(key, self.long.get(key, default))

    def rename_memory_key(memory_component, old_key, new_key):
        """
        Renames a key in a MemoryComponent, preserving its value
        and storage type (short-term vs. long-term).

        Args:
            memory_component (MemoryComponent): The entity's memory component.
            old_key (str): The name of the memory key to rename.
            new_key (str): The new name for the memory key.

        Returns:
            bool: True if the rename was successful, False if the old_key was not found.
        """
        # 1. Recall the value from the old key
        # We can't use mem.recall() because we need to know *where* it was stored
        value = None
        is_long_term = False

        if old_key in memory_component.short:
            value = memory_component.short[old_key]
            is_long_term = False
        elif old_key in memory_component.long:
            value = memory_component.long[old_key]
            is_long_term = True

        # 2. If the memory exists, proceed
        if value is not None:

            # 3. Remember the value with the new key, preserving its storage type
            memory_component.remember(new_key, value, long_term=is_long_term)

            # 4. Delete the old key from its original dictionary
            if is_long_term:
                del memory_component.long[old_key]
            else:
                del memory_component.short[old_key]

            return True  # Operation successful

        return False  # Old key not found

    def update(self, world):
        # Decrement TTL
        expired = []
        for key, (value, ttl) in self.short.items():
            ttl -= 1
            if ttl <= 0:
                expired.append(key)
            else:
                self.short[key] = (value, ttl)

        # Remove expired keys
        for key in expired:
            del self.short[key]

