# RP Engine

Goal:
A local roleplay engine that preserves character identity,
world continuity, and relationship evolution across sessions.

Core principles:

1. LLMs are stateless.
2. The engine owns memory.
3. The engine owns character evolution.
4. The engine owns world state.
5. Models are interchangeable.

Pipeline:

User Input
    ↓
Load Session
    ↓
Load Character State
    ↓
Load World State
    ↓
Build Prompt
    ↓
LLM Generation
    ↓
Extract Changes
    ↓
Update States
    ↓
Save Session

Data Layers:

Session Memory
    Current conversation

Character Memory
    Personality
    Relationships
    Long-term facts

World State
    Locations
    Events
    Timeline

Compressed Memory
    Summaries
    Key moments