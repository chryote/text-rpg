# entities/update_all.py

def UpdateAllEntities(world, macro, clock, region):
    for row in world:
        for tile in row:
            for ent in tile.entities:
                ent.update(world)

                # Remove payload
                if getattr(ent, "mark_for_removal", False):
                    tile.entities.remove(ent)

                    # also cleanup tile.payloads
                    if hasattr(tile, "payloads") and ent in tile.payloads:
                        tile.payloads.remove(ent)