# Implementation Rules

Before modifying code:

1. Inspect the existing architecture.
2. Respect existing boundaries.
3. Do not create new layers without justification.
4. Prefer the smallest working implementation.

When uncertain:

* Ask before changing architecture.
* Explain tradeoffs.
* Avoid large refactors.

The first milestone is a vertical slice, not a complete framework.

Do not add:

* Vector databases
* Agent frameworks
* Complex memory systems
* Extra abstractions

until they are required by the specification.
