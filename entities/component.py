# entities/component.py

class Component:
    def __init__(self, name):
        self.name = name
        self.entity = None  # will be assigned when attached

    def update(self, world):
        pass
