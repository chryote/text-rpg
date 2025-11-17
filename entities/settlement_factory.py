# entities/settlement_factory.py (snippet)
from .entity import Entity
from .components.perception import PerceptionComponent
from .components.memory import MemoryComponent
from .components.personality import PersonalityComponent
from .components.goals import GoalComponent
from .components.action import ActionComponent
from .components.settlement_ai import SettlementAIComponent
from .components.ai import AIComponent
from .components.emotion import EmotionComponent
from .components.diplomacy import DiplomacyComponent
from .components.relationship import RelationshipComponent


def CreateSettlementAI(tile):
    e = Entity(
        eid=f"settlement_{tile.x}_{tile.y}",
        etype="settlement_ai",
        tile=tile
    )
    e.add_component(PerceptionComponent(radius=5))
    e.add_component(MemoryComponent())
    e.add_component(PersonalityComponent())
    e.add_component(GoalComponent())
    e.add_component(ActionComponent())
    e.add_component(AIComponent())           # attach AI so SettlementAIComponent can bind its tree
    e.add_component(RelationshipComponent())
    e.add_component(EmotionComponent())
    e.add_component(DiplomacyComponent())
    e.add_component(SettlementAIComponent())
    # tile.entities.append(e)
    return e
