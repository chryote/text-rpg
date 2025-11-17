# ENTITY MODULAR COMPONENT SYSTEM

# entities/entity.py

class Entity:
    def __init__(self, eid, etype, tile):
        self.id = eid
        self.type = etype
        self.tile = tile
        self.components = {}
        self.alive = True

    # ---------------- COMPONENT MANIPULATION ----------------
    def add_component(self, comp):

        self.components[comp.name] = comp
        comp.entity = self
        return comp

    def get(self, name):
        return self.components.get(name)

    # ---------------- LIFECYCLE ----------------
    def update(self, world):
        for comp in self.components.values():
            comp.update(world)

    def to_json(self):
        data = {
            "id": self.id,
            "type": self.type,
            "tile": [self.tile.x, self.tile.y],
            "components": list(self.components.keys())
        }

        # Add relationship table if present
        if "relationship" in self.components:
            data["relationship"] = self.components["relationship"].to_json()

        return data

    def __repr__(self):
        return f"<Entity id={self.id} type={self.type}>"