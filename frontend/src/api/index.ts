import { z } from "zod";

const AdminUserSchema = z.object({
  id: z.string(),
  display_name: z.string(),
  telegram_external_id: z.string().nullable(),
  session_count: z.number(),
  is_blocked: z.boolean(),
});

const SessionDirectivesSchema = z.object({
  language: z.string(),
  rules: z.array(z.object({ id: z.string(), text: z.string() })),
  director_instructions: z.array(z.string()),
});

// Which memory layers the session runs (ADR-026). The recent conversation is absent on
// purpose: it is the story itself and cannot be switched off.
const SessionMemoryStateSchema = z.object({
  enabled_sources: z.array(z.string()),
  source_budget_shares: z.record(z.string(), z.number()),
});

// How close this session is to its next recap, in the same numbers the background worker
// uses. Token totals stop at the window edge; older messages are counted, not priced.
const MemoryStatusSchema = z.object({
  budget_tokens: z.number(),
  high_water_tokens: z.number(),
  window_tokens: z.number(),
  window_messages: z.number(),
  stored_messages: z.number(),
  turns_total: z.number(),
  covers_through_turn: z.number(),
  pending_turns: z.number(),
  behind_turns: z.number(),
  pending_tokens: z.number(),
  fold_batch_tokens: z.number(),
  summary_tokens: z.number(),
  summary_budget_tokens: z.number(),
  verbatim_turns: z.number(),
  whole_story_fits: z.boolean(),
  fold_progress: z.number(),
});

const SessionSummarySchema = z.object({
  summary: z.string(),
  covers_through_turn: z.number(),
  tokens: z.number(),
  model_name: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
});

const AdminSessionSchema = z.object({
  id: z.string(),
  scenario_definition_id: z.string(),
  owner_kind: z.string(),
  owner_id: z.string(),
  created_at: z.string(),
  updated_at: z.string(),
  // Set when a /restart or /clear superseded this session. It stays fully readable.
  deleted_at: z.string().nullable(),
  message_count: z.number().nullable(),
  directives: SessionDirectivesSchema,
  memory: SessionMemoryStateSchema,
  user_persona_name: z.string().nullable(),
  user_persona_description: z.string().nullable(),
});

const SessionMemorySchema = z.object({
  settings: SessionMemoryStateSchema,
  status: MemoryStatusSchema,
  summary: SessionSummarySchema.nullable(),
  // What the pass did, when the panel asked for one. Null on a plain read.
  last_pass: z.string().nullable(),
});

const AdminMessageSchema = z.object({
  role: z.string(),
  content: z.string(),
  metadata: z.record(z.string(), z.string()),
});

const DeletedMessageSchema = z.object({
  message: AdminMessageSchema,
  deleted_traces: z.number(),
});

const AdminTraceSchema = z.object({
  record: z.record(z.string(), z.unknown()),
});

const ScenarioSummarySchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  visibility: z.string(),
});

// Scenarios are edited as raw JSON (see docs/SCENARIOS.md) — the full payload is a nested
// document (world/characters/story_graph), so it's kept as a loose record rather than
// duplicating the whole shape in TS. The backend is the single source of validation truth
// (`scenario_definition_from_payload`).
const ScenarioPayloadSchema = z.record(z.string(), z.unknown());

const SessionExportSchema = z.object({
  session: z.record(z.string(), z.unknown()),
  transcript: z.array(z.record(z.string(), z.unknown())),
});

export type AdminUser = z.infer<typeof AdminUserSchema>;
export type SessionSummary = z.infer<typeof SessionSummarySchema>;
export type MemoryStatus = z.infer<typeof MemoryStatusSchema>;
export type SessionMemory = z.infer<typeof SessionMemorySchema>;
export type AdminSession = z.infer<typeof AdminSessionSchema>;
export type AdminMessage = z.infer<typeof AdminMessageSchema>;
export type AdminTrace = z.infer<typeof AdminTraceSchema>;
export type DeletedMessage = z.infer<typeof DeletedMessageSchema>;
export type ScenarioSummary = z.infer<typeof ScenarioSummarySchema>;
export type ScenarioPayload = z.infer<typeof ScenarioPayloadSchema>;
export type SessionExport = z.infer<typeof SessionExportSchema>;

class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`/admin${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    const message =
      detail && typeof detail === "object" && "detail" in detail
        ? String((detail as { detail: unknown }).detail)
        : response.statusText;
    throw new ApiError(response.status, message);
  }
  return schema.parse(await response.json());
}

export function listUsers(): Promise<AdminUser[]> {
  return request("/users", z.array(AdminUserSchema));
}

export function listUserSessions(userId: string): Promise<AdminSession[]> {
  return request(`/users/${userId}/sessions`, z.array(AdminSessionSchema));
}

export function getSession(sessionId: string): Promise<AdminSession> {
  return request(`/sessions/${sessionId}`, AdminSessionSchema);
}

export function getSessionTranscript(sessionId: string): Promise<AdminMessage[]> {
  return request(`/sessions/${sessionId}/transcript`, z.array(AdminMessageSchema));
}

export function getSessionTraces(sessionId: string): Promise<AdminTrace[]> {
  return request(`/sessions/${sessionId}/traces`, z.array(AdminTraceSchema));
}

export function deleteSession(sessionId: string): Promise<void> {
  return request(`/sessions/${sessionId}`, z.object({ status: z.string() }), {
    method: "DELETE",
  }).then(() => undefined);
}

// Last-only: deleting turn N requires deleting N+1 first. The server enforces it; the UI
// only offers the button on the final message.
export function deleteLastMessage(sessionId: string): Promise<DeletedMessage> {
  return request(`/sessions/${sessionId}/messages/last`, DeletedMessageSchema, {
    method: "DELETE",
  });
}

// Sets or replaces. This is the operator exception to the set-once contract: players can
// only change a persona with /clear, admins can correct one in place.
export function setSessionPersona(
  sessionId: string,
  name: string,
  description: string,
): Promise<AdminSession> {
  return request(`/sessions/${sessionId}/persona`, AdminSessionSchema, {
    method: "PUT",
    body: JSON.stringify({ name, description }),
  });
}

// Which layers run, how close the next recap is, and what the recap says — one call.
export function getSessionMemory(sessionId: string): Promise<SessionMemory> {
  return request(`/sessions/${sessionId}/memory`, SessionMemorySchema);
}

// One layer at a time, so a failed call leaves the other layers as they were.
export function setSessionMemorySource(
  sessionId: string,
  sourceId: string,
  enabled: boolean,
): Promise<SessionMemory> {
  return request(`/sessions/${sessionId}/memory`, SessionMemorySchema, {
    method: "PUT",
    body: JSON.stringify({ source_id: sourceId, enabled }),
  });
}

// Runs the summary pass now. It waits for the model, so it can take a while.
export function refreshSessionSummary(sessionId: string): Promise<SessionMemory> {
  return request(`/sessions/${sessionId}/memory/refresh`, SessionMemorySchema, {
    method: "POST",
  });
}

export function blockUser(userId: string): Promise<AdminUser> {
  return request(`/users/${userId}/block`, AdminUserSchema, { method: "POST" });
}

export function unblockUser(userId: string): Promise<AdminUser> {
  return request(`/users/${userId}/unblock`, AdminUserSchema, { method: "POST" });
}

export function listScenarios(): Promise<ScenarioSummary[]> {
  return request("/scenarios", z.array(ScenarioSummarySchema));
}

export function getScenario(scenarioId: string): Promise<ScenarioPayload> {
  return request(`/scenarios/${scenarioId}`, ScenarioPayloadSchema);
}

export function createScenario(payload: ScenarioPayload): Promise<ScenarioPayload> {
  return request("/scenarios", ScenarioPayloadSchema, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateScenario(
  scenarioId: string,
  payload: ScenarioPayload,
): Promise<ScenarioPayload> {
  return request(`/scenarios/${scenarioId}`, ScenarioPayloadSchema, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function exportSession(sessionId: string): Promise<SessionExport> {
  return request(`/sessions/${sessionId}/export`, SessionExportSchema);
}

export { ApiError };
