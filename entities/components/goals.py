# entities/components/goals.py

from ..component import Component

class GoalComponent(Component):
    def __init__(self):
        super().__init__("goals")
        self.goals = []

    def push(self, goal):
        self.goals.append(goal)

    def pop(self):
        return self.goals.pop(0) if self.goals else None
