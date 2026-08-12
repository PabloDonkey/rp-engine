import { z } from "zod";

/**
 * The scenario payload, typed on the client.
 *
 * This mirrors `scenario_definition_from_payload` in
 * `src/rp_engine/infrastructure/scenario_serialization.py`. The server stays the single
 * source of validation truth — this schema exists so the form can name the field that is
 * wrong before a save leaves the browser, and so the panel stops treating a scenario as an
 * untyped blob.
 *
 * Keep the two in step. A field added on the server and not here is a field the form
 * silently drops on save.
 */

/** The owner every scenario written through the panel belongs to. */
export const SYSTEM_OWNER_ID = "00000000-0000-0000-0000-000000000000";

/**
 * Scenario ids reach the user as `/play <id>` over Telegram, so they stay short and
 * typable: lowercase letters, digits, and single separators between them.
 */
export const SCENARIO_ID_PATTERN = /^[a-z0-9]+(?:[-_][a-z0-9]+)*$/;

export const VISIBILITY_VALUES = ["PUBLIC", "UNLISTED", "RESTRICTED"] as const;

/**
 * A metadata value is one string or a list of strings — the same model the server holds
 * (`core/metadata.py`). Anything deeper has no control on the form and the server refuses
 * it.
 */
export const MetadataSchema = z.record(
  z.string(),
  z.union([z.string(), z.array(z.string())]),
);

export const WorldSchema = z.object({
  id: z.string().min(1, "World id is required"),
  name: z.string().min(1, "World name is required"),
  description: z.string(),
  rules: z.array(z.string()),
  metadata: MetadataSchema,
});

export const CharacterSchema = z.object({
  id: z.string().min(1, "Character id is required"),
  name: z.string().min(1, "Character name is required"),
  description: z.string(),
  personality: z.string(),
  greeting: z.string(),
  metadata: MetadataSchema,
});

export const StoryBeatSchema = z.object({
  id: z.string().min(1),
  description: z.string(),
  transitions: z.record(z.string(), z.string()),
  metadata: MetadataSchema,
});

export const StoryGraphSchema = z.object({
  beats: z.record(z.string(), StoryBeatSchema),
  entry_beat_id: z.string().nullable(),
  metadata: MetadataSchema,
});

/**
 * The id rule the *create* form applies.
 *
 * Deliberately not part of `ScenarioDefinitionSchema`: reading is not the place to enforce
 * a naming rule. A scenario stored before this rule existed must still open in the panel,
 * and a schema that refused it would break the page rather than flag the id.
 */
export const ScenarioIdSchema = z
  .string()
  .min(1, "Id is required")
  .regex(SCENARIO_ID_PATTERN, "Use lowercase letters, digits, and single dashes between them");

export const ScenarioDefinitionSchema = z.object({
  id: z.string().min(1, "Id is required"),
  owner_id: z.string().min(1),
  name: z.string().min(1, "Name is required"),
  description: z.string(),
  // Off means no world section in the prompt. It must write null, not an object of empty
  // strings, or the prompt gains a blank world block.
  world: WorldSchema.nullable(),
  // Keyed by role, not by character id. The role is what the scenario calls this part.
  characters: z.record(z.string(), CharacterSchema),
  // Order matters: the prompt lists these rules in this order.
  rules: z.array(z.string()),
  // Inert data. No scenario uses it yet, and the form keeps it as raw JSON.
  story_graph: StoryGraphSchema.nullable(),
  initial_context: z.string(),
  visibility: z.enum(VISIBILITY_VALUES),
  // Only read when the visibility is RESTRICTED.
  allowed_group_chat_ids: z.array(z.string()),
  metadata: MetadataSchema,
});

export type Metadata = z.infer<typeof MetadataSchema>;
export type MetadataValue = Metadata[string];
export type World = z.infer<typeof WorldSchema>;
export type Character = z.infer<typeof CharacterSchema>;
export type StoryBeat = z.infer<typeof StoryBeatSchema>;
export type StoryGraph = z.infer<typeof StoryGraphSchema>;
export type ScenarioDefinition = z.infer<typeof ScenarioDefinitionSchema>;
export type ScenarioVisibility = ScenarioDefinition["visibility"];

/**
 * A blank scenario for the create form.
 *
 * A fresh object every call, never a shared constant: the form edits it in place, and one
 * shared object would carry the last draft into the next new scenario.
 */
export function emptyScenario(): ScenarioDefinition {
  return {
    id: "",
    owner_id: SYSTEM_OWNER_ID,
    name: "",
    description: "",
    world: null,
    characters: {},
    rules: [],
    story_graph: null,
    initial_context: "",
    visibility: "PUBLIC",
    allowed_group_chat_ids: [],
    metadata: {},
  };
}

/** A blank world, for when the form's world toggle is switched on. */
export function emptyWorld(): World {
  return { id: "", name: "", description: "", rules: [], metadata: {} };
}

/** A blank character, for a new role card. */
export function emptyCharacter(): Character {
  return { id: "", name: "", description: "", personality: "", greeting: "", metadata: {} };
}

/**
 * The role keys that appear more than once.
 *
 * The payload keys characters by role, so a repeat is not merely invalid — the later card
 * silently overwrites the earlier one. The form edits characters as a list, so it has to
 * catch this before turning the list back into an object.
 */
export function duplicateRoleKeys(roles: readonly string[]): string[] {
  const seen = new Set<string>();
  const repeated = new Set<string>();
  for (const role of roles) {
    if (seen.has(role)) {
      repeated.add(role);
    }
    seen.add(role);
  }
  return [...repeated];
}
