import { describe, expect, test } from "vitest";

import {
  ScenarioDefinitionSchema,
  ScenarioIdSchema,
  duplicateRoleKeys,
  emptyCharacter,
  emptyScenario,
  emptyWorld,
} from "@/api/scenarioSchema";

/** A payload shaped exactly as `scenario_definition_to_payload` writes it. */
function serverPayload() {
  return {
    id: "sealed-vault",
    owner_id: "00000000-0000-0000-0000-000000000000",
    name: "The Sealed Vault",
    description: "A heist.",
    world: {
      id: "old-city",
      name: "The Old City",
      description: "Damp stone.",
      rules: ["Magic is rare."],
      metadata: { era: ["1920s"] },
    },
    characters: {
      narrator: {
        id: "narrator",
        name: "Narrator",
        description: "A voice.",
        personality: "Dry.",
        greeting: "",
        metadata: {},
      },
    },
    rules: ["Stay in character.", "Answer questions directly."],
    story_graph: null,
    initial_context: "You crouch by the door.",
    visibility: "PUBLIC",
    allowed_group_chat_ids: [],
    metadata: { genre: "heist", tags: ["noir", "crime"] },
  };
}

describe("ScenarioDefinitionSchema", () => {
  test("accepts a payload in the shape the server writes", () => {
    const parsed = ScenarioDefinitionSchema.parse(serverPayload());

    expect(parsed.metadata).toEqual({ genre: "heist", tags: ["noir", "crime"] });
    expect(parsed.world?.metadata).toEqual({ era: ["1920s"] });
    // Rule order is load-bearing: the prompt lists them in this order.
    expect(parsed.rules).toEqual(["Stay in character.", "Answer questions directly."]);
  });

  test.each([
    ["id", "Id is required"],
    ["name", "Name is required"],
  ])("names the field when %s is empty", (field, message) => {
    const result = ScenarioDefinitionSchema.safeParse({ ...serverPayload(), [field]: "" });

    expect(result.success).toBe(false);
    expect(result.error?.issues[0]?.path).toEqual([field]);
    expect(result.error?.issues[0]?.message).toBe(message);
  });

  test("refuses a visibility the server does not have", () => {
    const result = ScenarioDefinitionSchema.safeParse({
      ...serverPayload(),
      visibility: "SECRET",
    });

    expect(result.success).toBe(false);
  });

  test("refuses metadata deeper than a string or a list of strings", () => {
    // The form has no control for a nested object, and the server refuses it too.
    const result = ScenarioDefinitionSchema.safeParse({
      ...serverPayload(),
      metadata: { credits: { writer: "someone" } },
    });

    expect(result.success).toBe(false);
  });

  test("still reads a scenario whose id predates the slug rule", () => {
    // Reading is not the place to enforce a naming rule: refusing here would break the
    // page instead of flagging the id.
    const parsed = ScenarioDefinitionSchema.safeParse({
      ...serverPayload(),
      id: "Legacy_ID 2019",
    });

    expect(parsed.success).toBe(true);
  });
});

describe("ScenarioIdSchema", () => {
  test.each(["sealed-vault", "haunted-manor", "vault2", "a_b"])("accepts %s", (id) => {
    expect(ScenarioIdSchema.safeParse(id).success).toBe(true);
  });

  test.each(["", "Sealed-Vault", "sealed vault", "-vault", "vault-", "sealed--vault"])(
    "refuses %s",
    (id) => {
      expect(ScenarioIdSchema.safeParse(id).success).toBe(false);
    },
  );
});

describe("the empty factories", () => {
  test("an empty scenario passes everything except the required text", () => {
    const blank = emptyScenario();

    expect(blank.world).toBeNull();
    expect(blank.story_graph).toBeNull();
    expect(blank.characters).toEqual({});
    expect(blank.visibility).toBe("PUBLIC");

    const result = ScenarioDefinitionSchema.safeParse(blank);
    expect(result.success).toBe(false);
    // Only the two fields a person has to type are missing.
    expect(result.error?.issues.map((issue) => issue.path.join("."))).toEqual(["id", "name"]);
  });

  test("each call returns a fresh object", () => {
    // One shared constant would carry the last draft into the next new scenario.
    const first = emptyScenario();
    first.name = "Draft";

    expect(emptyScenario().name).toBe("");
    expect(emptyWorld()).not.toBe(emptyWorld());
    expect(emptyCharacter()).not.toBe(emptyCharacter());
  });
});

describe("duplicateRoleKeys", () => {
  test("finds a repeated role", () => {
    // Characters are keyed by role, so a repeat silently overwrites the earlier card.
    expect(duplicateRoleKeys(["narrator", "rival", "narrator"])).toEqual(["narrator"]);
  });

  test("reports each repeated role once", () => {
    expect(duplicateRoleKeys(["a", "a", "a", "b", "b"])).toEqual(["a", "b"]);
  });

  test("finds nothing when every role is distinct", () => {
    expect(duplicateRoleKeys(["narrator", "rival"])).toEqual([]);
    expect(duplicateRoleKeys([])).toEqual([]);
  });
});
