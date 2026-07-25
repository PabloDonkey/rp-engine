import { z } from "zod";

const AdminUserSchema = z.object({
  id: z.string(),
  display_name: z.string(),
  telegram_external_id: z.string().nullable(),
  session_count: z.number(),
  is_blocked: z.boolean(),
});

const AdminSessionSchema = z.object({
  id: z.string(),
  scenario_definition_id: z.string(),
  owner_kind: z.string(),
  owner_id: z.string(),
  created_at: z.string(),
  message_count: z.number().nullable(),
});

const AdminMessageSchema = z.object({
  role: z.string(),
  content: z.string(),
  metadata: z.record(z.string(), z.string()),
});

const AdminTraceSchema = z.object({
  record: z.record(z.string(), z.unknown()),
});

export type AdminUser = z.infer<typeof AdminUserSchema>;
export type AdminSession = z.infer<typeof AdminSessionSchema>;
export type AdminMessage = z.infer<typeof AdminMessageSchema>;
export type AdminTrace = z.infer<typeof AdminTraceSchema>;

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

export function blockUser(userId: string): Promise<AdminUser> {
  return request(`/users/${userId}/block`, AdminUserSchema, { method: "POST" });
}

export function unblockUser(userId: string): Promise<AdminUser> {
  return request(`/users/${userId}/unblock`, AdminUserSchema, { method: "POST" });
}

export { ApiError };
