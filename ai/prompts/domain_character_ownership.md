Update DOMAIN_MODEL.md to document three missing domain concepts. This is a documentation-only change. Do not modify implementation or architecture documents.

## Goals

Improve the domain model before the PostgreSQL migration by explicitly modeling:

1. Character ownership
2. Character Definition vs Character State
3. Character visibility

Maintain the existing style, formatting, terminology, and Mermaid diagrams used throughout DOMAIN_MODEL.md.

---

## 1. Add "Character Ownership"

Introduce a new section explaining that every Character has exactly one owner.

Include:

- User owns Character
- One User can own many Characters
- One Character has exactly one owner
- Ownership is permanent unless explicitly transferred (future feature)
- Characters exist independently from conversations

Include a Mermaid relationship diagram similar to:

User
 └── owns ──► Character

Also document the cardinality:

User (1) ---> (*) Character

---

## 2. Add "Character Definition vs Character State"

This is an important domain distinction.

Document that Character represents a reusable template while Character State represents evolving runtime data.

Character Definition should include examples such as:

- name
- personality
- description
- appearance
- scenario
- rules
- system prompt
- initial world context

Character State should include examples such as:

- relationship
- memories
- emotional state
- inventory
- location
- story progression
- learned knowledge
- evolution
- persistent variables

Clearly explain:

- Character Definition changes rarely.
- Character State evolves continuously.
- Multiple Character States may exist for the same Character.
- Character State is conversation-specific (or future identity-specific).
- This separation enables reusable characters with independent story progression.

Include a simple Mermaid diagram showing:

Character
    ├── Character State A
    ├── Character State B
    └── Character State C

Each state evolves independently.

Mention that this separation is expected to map naturally to separate persistence entities during the PostgreSQL migration.

---

## 3. Add "Character Visibility"

Introduce a CharacterVisibility enumeration.

Document:

- PRIVATE
- SHARED
- PUBLIC

Explain each:

PRIVATE
- only owner can use
- current implementation

SHARED
- future feature
- available only to explicitly authorized users or groups

PUBLIC
- future feature
- discoverable and usable by everyone

Clarify that visibility affects access only.

Ownership remains unchanged regardless of visibility.

---

## Documentation requirements

- Keep the document implementation-agnostic.
- Do not discuss SQL schemas or table definitions.
- Do not modify existing concepts unless necessary for consistency.
- Integrate the new sections where they fit naturally within the current Domain Model.
- Preserve existing Markdown style, headings, Mermaid syntax, terminology, and formatting.
- Ensure all new concepts remain consistent with ARCHITECTURE.md, DECISIONS.md, and the planned PostgreSQL migration.