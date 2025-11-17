INSIDE DIRECTORY docs/

# Project Vision Summary

## Overview
This project is not a quest-driven RPG.  
It is a **story-generating world simulation text RPG**, where systems interact to produce rich, emergent narrative moments.  
The goal is not realism — the goal is **meaningful friction**, expressive tags, and dynamic stories.

The world is built from **macro-level simulation** down to **granular entity interactions** and **scene-based micro-narratives**.

---

## 1. Macro World Simulation (Tile-Level)
The foundation is a fully simulated procedural world:

- climate, humidity, rainfall  
- biomes and ecosystems  
- soil, resources, terrain features  
- settlements and population  
- trade routes and economics  
- region traits and world events  

These systems generate **high-level tags**, such as:

- `prosperous`, `struggling`, `supplies_deficit`  
- `bandit_settlement`, `trade_hub`  
- `dangerous_pass`, `eco_collapse`, `predator_surge`  
- `frontier_region`, `market_center`  

**Purpose:** Create world-scale tensions and opportunities that shape stories.

---

## 2. Trade Routes as Interaction Arteries
Trade routes serve as the **main stage for macro interaction**:

- caravans traveling between settlements  
- diplomatic movement  
- bandit ambushes  
- market fluctuations  
- faction influence  
- weather and ecological hazards  

A DnD-style **dice + bias system** determines events on these routes, using:

- settlement relationships (ally/rival)  
- wealth, stability, military strength  
- route danger, ecosystem risk  
- trade value and factional tension  

These trigger dynamic route events:
- sabotage, cooperation, festivals  
- ambushes, tariffs, negotiations  
- legendary or disastrous encounters  

Tags update accordingly, shaping future interactions.

---

## 3. Tile-Scoped Granular Simulation
Each tile becomes a **micro-ecosystem** with:

- local NPC groups  
- wildlife activity  
- hazards and geography  
- neighborhood gossip  
- tensions and rumors  
- local event queues  

These tiles reflect the world’s ongoing changes and feed **mid-scale narrative tension**.

---

## 4. Entities as Event-Driven Actors
Entities do not simulate life minute-by-minute.  
They **react to world tags**, driven by:

- personality  
- motivations  
- fears and desires  
- social roles  
- faction ties  
- local environment  

Examples:
- A hunter reacts to `predator_surge`  
- A merchant responds to `trade_route_disrupted`  
- A bandit group exploits `struggling` settlements  
- A priest interprets `ecological_collapse` as an omen  

Entities produce events, propagate rumors, and create narrative pressure.

---

## 5. Scene System (High-Resolution Story Moments)
When the player or key entities are nearby, the simulation **zooms in** to a Scene:

Examples:
- tavern disputes  
- caravan negotiations  
- ambush encounters  
- council meetings  
- rituals or festivals  
- family arguments  
- environmental threats  

Scenes use:
- tile tags  
- entity personalities  
- settlement conditions  
- trade events  
- faction tensions  

Scenes generate dialogue, micro-drama, and consequences, then feed back into the world simulation.

---

## 6. Philosophy
This project **does not aim for perfect realism**.  
Every system exists for one purpose:

**To produce rich narrative tags and dynamic interactions.**

The world is a **story ecology**, not a strict simulation.  
Systems are stylized, biased, and tuned for drama.

---

## 7. Intended Output
A world that:

- feels alive  
- reacts to itself  
- produces emergent storylines  
- evolves through conflict and cooperation  
- generates local and global narrative hooks  
- gives players scenes shaped by the world state  

No scripted quests.  
No forced plot lines.  
Just **emergent storytelling grounded in systemic world simulation**.

---

## Summary in One Sentence
**A tag-driven, systemic storytelling engine where macro world events, trade interactions, tile-level dynamics, and entity-driven scenes combine to create an endlessly emergent narrative world.**
