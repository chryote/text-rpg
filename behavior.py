# directory behavior.py/

import random

class Status:
    SUCCESS = 'SUCCESS'
    FAILURE = 'FAILURE'
    WARNING = 'WARNING'


# --- Behavior tree base classes (kept unchanged)
class Node:
    def tick(self):
        raise NotImplementedError


class Sequence(Node):
    def __init__(self, children):
        self.children = children

    def tick(self):
        for child in self.children:
            status = child.tick()
            if status != Status.SUCCESS:
                return status
        return Status.SUCCESS


class Selector(Node):
    def __init__(self, children):
        self.children = children

    def tick(self):
        for child in self.children:
            status = child.tick()
            if status != Status.FAILURE:
                return status
        return Status.FAILURE


# --- NPC behavior (uses global random; keep separate from world RNG)
class IsEnemyVisible(Node):
    def tick(self):
        visible = random.choice([True, False])
        print(f"Is enemy visible? {visible}")
        return Status.SUCCESS if visible else Status.FAILURE


class AttackEnemy(Node):
    def tick(self):
        print("Attacking enemy!")
        return Status.SUCCESS


class Patrol(Node):
    def tick(self):
        print("Patrolling area...")
        return Status.SUCCESS


def DebugNPCBehavior():
    # If enemy visible -> attack
    # Otherwise -> patrol
    root = Selector([
        Sequence([IsEnemyVisible(), AttackEnemy()]),
        Sequence([IsEnemyVisible(), AttackEnemy()]),
        Patrol()
    ])

    for i in range(5):
        print(f"\nTick {i + 1}")
        root.tick()