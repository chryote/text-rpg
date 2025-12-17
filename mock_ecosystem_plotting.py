# mock_ecosystem_plotting.py
# Entry point for plotting simulation data, as referenced in README.md

import random
# Need matplotlib for plotting (though imported in worldsim, it's good practice here too)
import matplotlib.pyplot as plt

# Import the necessary functions from your project structure
from main import CreateWorld
from worldsim import RunHistorySimulation, PlotEcosystemHistory

def RunEcosystemTest():
    """
    Initializes a world, runs the ecosystem simulation for a set number of steps,
    and plots the results for a single tile to visualize the emergent dynamics.
    """
    # --- Setup ---
    master_seed = 42 # Fixed seed for reproducible simulation results
    rng = random.Random(master_seed)

    # 1. Create a fully initialized world object
    print(f"Creating world with seed {master_seed}...")
    # CreateWorld handles the full pipeline: climate, biomes, resources, ecosystems, etc.
    world, macro = CreateWorld(master_seed=master_seed)

    # Set sample coordinates. Using (10, 10) for the 20x20 world size defined in main.py.
    sample_coords = (10, 10)

    # Simulation duration. 400 steps will show multiple cycles of the Lotka-Volterra dynamics.
    simulation_steps = 100

    print(f"Running ecosystem simulation for {simulation_steps} steps at tile {sample_coords}...")

    # 2. Run the simulation and collect history
    # RunHistorySimulation will call SimulateTrophicEcosystem iteratively.
    history = RunHistorySimulation(
        world=world,
        rng=rng,
        steps=simulation_steps,
        sample_coords=sample_coords
    )

    # 3. Plot the history
    print("Generating plot of trophic dynamics...")
    # PlotEcosystemHistory will use matplotlib to display the graph.
    PlotEcosystemHistory(history, sample_coords)

    print(f"Plot complete. The graph shows the oscillating populations of Producers, Herbivores, and Carnivores over time at tile {sample_coords}.")

if __name__ == '__main__':
    RunEcosystemTest()