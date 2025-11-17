# entities/components/ai.py
from ..component import Component

class AIComponent(Component):
    def __init__(self, behavior_tree=None):
        super().__init__("ai")
        self.behavior_tree = behavior_tree
        self.blackboard = {}

    def update(self, world):
        if self.behavior_tree:
            # behavior tree nodes may rely on entity reference
            try:
                self.behavior_tree.tick()
            except Exception:
                # be defensive: don't crash simulation on BT error
                pass
