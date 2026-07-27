import { defineStore } from "pinia";

import * as api from "@/api";
import type {
  AdminMessage,
  DeletedMessage,
  AdminSession,
  AdminTrace,
  AdminUser,
  ScenarioPayload,
  ScenarioSummary,
} from "@/api";

function toSummary(payload: ScenarioPayload): ScenarioSummary {
  return {
    id: String(payload.id ?? ""),
    name: String(payload.name ?? ""),
    description: String(payload.description ?? ""),
    visibility: String(payload.visibility ?? ""),
  };
}

export const useAdminStore = defineStore("admin", {
  state: () => ({
    users: [] as AdminUser[],
    usersLoading: false,
    usersError: null as string | null,

    sessions: [] as AdminSession[],
    sessionsLoading: false,
    sessionsError: null as string | null,

    session: null as AdminSession | null,
    transcript: [] as AdminMessage[],
    traces: [] as AdminTrace[],
    sessionLoading: false,
    sessionError: null as string | null,

    scenarios: [] as ScenarioSummary[],
    scenariosLoading: false,
    scenariosError: null as string | null,

    scenario: null as ScenarioPayload | null,
    scenarioLoading: false,
    scenarioError: null as string | null,
  }),
  actions: {
    async fetchUsers(): Promise<void> {
      this.usersLoading = true;
      this.usersError = null;
      try {
        this.users = await api.listUsers();
      } catch (error) {
        this.usersError = error instanceof Error ? error.message : String(error);
      } finally {
        this.usersLoading = false;
      }
    },

    async fetchUserSessions(userId: string): Promise<void> {
      this.sessionsLoading = true;
      this.sessionsError = null;
      try {
        this.sessions = await api.listUserSessions(userId);
      } catch (error) {
        this.sessionsError = error instanceof Error ? error.message : String(error);
      } finally {
        this.sessionsLoading = false;
      }
    },

    async fetchSessionDetail(sessionId: string): Promise<void> {
      this.sessionLoading = true;
      this.sessionError = null;
      try {
        const [session, transcript, traces] = await Promise.all([
          api.getSession(sessionId),
          api.getSessionTranscript(sessionId),
          api.getSessionTraces(sessionId),
        ]);
        this.session = session;
        this.transcript = transcript;
        this.traces = traces;
      } catch (error) {
        this.sessionError = error instanceof Error ? error.message : String(error);
      } finally {
        this.sessionLoading = false;
      }
    },

    async deleteSession(sessionId: string): Promise<void> {
      await api.deleteSession(sessionId);
      this.sessions = this.sessions.filter((s) => s.id !== sessionId);
    },

    async deleteLastMessage(sessionId: string): Promise<DeletedMessage> {
      const deleted = await api.deleteLastMessage(sessionId);
      this.transcript = this.transcript.slice(0, -1);
      // The turn's traces were deleted server-side with it; refetch so the per-message debug
      // filters cannot attach a stale trace to whatever is now last.
      this.traces = await api.getSessionTraces(sessionId);
      return deleted;
    },

    async toggleBlock(user: AdminUser): Promise<void> {
      const updated = user.is_blocked
        ? await api.unblockUser(user.id)
        : await api.blockUser(user.id);
      const index = this.users.findIndex((u) => u.id === user.id);
      if (index !== -1) {
        this.users[index] = updated;
      }
    },

    async fetchScenarios(): Promise<void> {
      this.scenariosLoading = true;
      this.scenariosError = null;
      try {
        this.scenarios = await api.listScenarios();
      } catch (error) {
        this.scenariosError = error instanceof Error ? error.message : String(error);
      } finally {
        this.scenariosLoading = false;
      }
    },

    async fetchScenario(scenarioId: string): Promise<void> {
      this.scenarioLoading = true;
      this.scenarioError = null;
      try {
        this.scenario = await api.getScenario(scenarioId);
      } catch (error) {
        this.scenarioError = error instanceof Error ? error.message : String(error);
      } finally {
        this.scenarioLoading = false;
      }
    },

    // Unlike the fetch* actions above, this does not catch — the edit page shows the
    // validation error inline next to the JSON textarea rather than as a page-level banner.
    async createScenario(payload: ScenarioPayload): Promise<ScenarioPayload> {
      const created = await api.createScenario(payload);
      this.scenarios.push(toSummary(created));
      return created;
    },

    async updateScenario(scenarioId: string, payload: ScenarioPayload): Promise<ScenarioPayload> {
      const updated = await api.updateScenario(scenarioId, payload);
      const index = this.scenarios.findIndex((s) => s.id === scenarioId);
      if (index !== -1) {
        this.scenarios[index] = toSummary(updated);
      }
      return updated;
    },
  },
});
