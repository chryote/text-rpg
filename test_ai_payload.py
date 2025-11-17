# tests/test_ai_payload.py

from main import CreateWorld
from entities.update_all import UpdateAllEntities
from timesim import TimeSystem
from event_manager import EventManager
from tile_events import TriggerTileEvents, TriggerEventFromLibrary, ScheduleTileEvent
from economy import GetAllSettlementIDs, GetSettlementByID
from trade_routes import GenerateTradeRoutes
from world_index import WorldIndex
import world_index_store

def find_two_settlements(world):
    """Return first two tiles that have settlement AI entities."""
    settlements = []
    for row in world:
        for tile in row:
            for ent in tile.entities:
                if ent.type == "settlement_ai":
                    settlements.append((tile, ent))
                    if len(settlements) == 2:
                        return settlements
    return None, None


def show_info(tile, label):
    econ = tile.get_system("economy")
    print(f"\n--- {label} ({tile.x},{tile.y}) ---")
    print("Supplies:", econ.get("supplies"))
    print("Wealth:", econ.get("wealth"))
    print("Tags:", tile.tags)

    for ent in tile.entities:
        if ent.type == "settlement_ai":
            rel = ent.components.get("relationship")
            if rel:
                print("Relationships:", rel.to_json())


def main():

    print("=== GENERATING REAL WORLD VIA CreateWorld() ===")
    world, macro = CreateWorld(world_time=0, master_seed=1234)

    # Build index
    world_index = WorldIndex(world)

    # Store into global access point
    world_index_store.world_index = world_index

    # Attach index into each tile
    for row in world:
        for tile in row:
            tile.index = world_index

    trade_links = GenerateTradeRoutes(world)
    # store trade_links in tile (0,0) meta
    meta = world[0][0].get_system("meta")
    meta["trade_links"] = trade_links

    print ("some trade links:", trade_links[1646][0])

    # Settlement economy + agents already created by:
    # InitializeSettlementEconomy
    # AttachSettlementAgents

    # ----------------------------------------------------
    # Select two settlement tiles for testing
    # ----------------------------------------------------
    (sender_tile, sender_ai), (receiver_tile, receiver_ai) = find_two_settlements(world)

    print(f"\nChosen settlements:")
    print(f" Sender:   ({sender_tile.x},{sender_tile.y}) with ID: {sender_tile.get_system("economy")["id"]}")
    print(f" Receiver: ({receiver_tile.x},{receiver_tile.y})with ID: {receiver_tile.get_system("economy")["id"]}")

    # ----------------------------------------------------
    # Force sender into supply crisis so AI triggers trade_mission
    # ----------------------------------------------------
    econ = sender_tile.get_system("economy")
    sender_tile.temp_dest = receiver_tile
    sender_tile.world_reference = world
    econ["supplies"] = 1   # critical low
    econ["population"] = max(10, econ.get("population", 10))

    print("\n=== BEFORE SIMULATION ===")
    show_info(sender_tile, "SENDER INITIAL")
    show_info(receiver_tile, "RECEIVER INITIAL")

    # ----------------------------------------------------
    # TIME SYSTEM + EVENT MANAGER
    # ----------------------------------------------------
    print("\n=== RUNNING AI TICKS VIA TimeSystem ===")

    settlement_ids = GetAllSettlementIDs(world)
    print ("SETTLEMENT IDS:", settlement_ids)

    tile, econ = GetSettlementByID(world, settlement_ids[0])

    time_system = TimeSystem(start_day=0, start_hour=6)
    event_manager = EventManager(world, macro, time_system)

    # Register as hourly task
    event_manager.register_hourly(UpdateAllEntities)
    event_manager.register_interval(1, TriggerTileEvents)

    TriggerEventFromLibrary(tile, "market_boom")

    # ----------------------------------------------------
    # Run ~2 days of hourly ticks so AI triggers trade_mission
    # ----------------------------------------------------
    time_system.run(hours=300)

    print("\nEntities on sender tile:", [e.type for e in sender_tile.entities])

    # ----------------------------------------------------
    # Now simulate enough ticks so payload arrives
    # (payload follows path via PhysicalComponent)
    # ----------------------------------------------------
    # print("\n=== SIMULATING MOVEMENT UNTIL PAYLOAD ARRIVES ===")
    # for _ in range(300):
    #     UpdateAllEntities(world, macro, time_system, None)

    print("\n=== AFTER SIMULATION ===")
    show_info(sender_tile, "SENDER FINAL")
    show_info(receiver_tile, "RECEIVER FINAL")


if __name__ == "__main__":
    main()
