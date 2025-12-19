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
from .components.tendency import TendencyComponent
from .components.meta_emotion import MetaEmotionComponent
from .components.meta_perception import MetaPerceptionComponent
from .components.meta_personality import MetaPersonalityComponent
from .components.meta_relationship import MetaRelationshipComponent


def CreateSettlementAI(tile):
    e = Entity(
        eid=f"settlement_{tile.x}_{tile.y}",
        etype="settlement_ai",
        tile=tile
    )

    geo_pressure = tile.get_system("geo_pressure") or {
        "resource_stability": 0, "environmental_threat": 0,
        "mobility_constraint": 0, "isolation_level": 0
    }
    Tendency = TendencyComponent()
    Tendency.apply_geo_bias(geo_pressure)

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
    e.add_component(Tendency)
    e.add_component(MetaEmotionComponent())
    e.add_component(MetaPerceptionComponent())
    e.add_component(MetaPersonalityComponent())
    e.add_component(MetaRelationshipComponent())
    # tile.entities.append(e)
    return e
