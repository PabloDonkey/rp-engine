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
  SessionMemory,
} from "@/api";

// A save answers with the scenario, not with a list row, so the row is rebuilt here rather
// than re-fetching the whole list. `session_count` is not in that answer: a save cannot
// change how many stories are running, so the existing count is kept.
function toSummary(payload: ScenarioPayload, sessionCount = 0): ScenarioSummary {
  return {
    id: payload.id,
    name: payload.name,
    description: payload.description,
    visibility: payload.visibility,
    session_count: sessionCount,
    is_active: true,
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
    // Errors from an action (delete, block…) rather than from loading the page. Kept apart
    // from sessionError because that one *replaces* the view: a failed delete must leave the
    // transcript on screen, not blank it.
    actionError: null as string | null,
    traces: [] as AdminTrace[],
    // Memory layer state for the open session: which layers run, how close the next
    // recap is, and what the recap says. Null until the session detail is loaded.
    sessionMemory: null as SessionMemory | null,
    memoryBusy: false,
    sessionLoading: false,
    sessionError: null as string | null,

    scenarios: [] as ScenarioSummary[],
    scenariosLoading: false,
    scenariosError: null as string | null,
    // Whether the list on screen includes retired scenarios. Off by default, and kept in
    // state so a retire or restore can re-read the list the operator is actually looking at.
    scenariosIncludeInactive: false,

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
      // Loading a session clears any stale action error, so one failed delete does not
      // follow the user onto a different session.
      this.actionError = null;
      try {
        const [session, transcript, traces, memory] = await Promise.all([
          api.getSession(sessionId),
          api.getSessionTranscript(sessionId),
          api.getSessionTraces(sessionId),
          api.getSessionMemory(sessionId),
        ]);
        this.session = session;
        this.transcript = transcript;
        this.traces = traces;
        this.sessionMemory = memory;
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

    async deleteLastMessage(sessionId: string): Promise<DeletedMessage | null> {
      this.actionError = null;
      try {
        const deleted = await api.deleteLastMessage(sessionId);
        // Re-read rather than splicing locally: the server is the authority on what is left,
        // and this also refreshes message_count and the traces that were deleted with the
        // turn. A silently-diverging local copy is what makes a failed delete look like a
        // delete that "did not refresh".
        await this.fetchSessionDetail(sessionId);
        return deleted;
      } catch (error) {
        this.actionError = error instanceof Error ? error.message : String(error);
        return null;
      }
    },

    async setSessionPersona(
      sessionId: string,
      name: string,
      description: string,
    ): Promise<boolean> {
      this.actionError = null;
      try {
        this.session = await api.setSessionPersona(sessionId, name, description);
        return true;
      } catch (error) {
        this.actionError = error instanceof Error ? error.message : String(error);
        return false;
      }
    },

    async setSessionMemorySource(
      sessionId: string,
      sourceId: string,
      enabled: boolean,
    ): Promise<boolean> {
      this.actionError = null;
      this.memoryBusy = true;
      try {
        this.sessionMemory = await api.setSessionMemorySource(sessionId, sourceId, enabled);
        return true;
      } catch (error) {
        this.actionError = error instanceof Error ? error.message : String(error);
        return false;
      } finally {
        this.memoryBusy = false;
      }
    },

    // Runs the summary pass now. It waits for the model, so the caller shows the button as
    // busy until this resolves.
    async refreshSessionSummary(sessionId: string): Promise<boolean> {
      this.actionError = null;
      this.memoryBusy = true;
      try {
        this.sessionMemory = await api.refreshSessionSummary(sessionId);
        return true;
      } catch (error) {
        this.actionError = error instanceof Error ? error.message : String(error);
        return false;
      } finally {
        this.memoryBusy = false;
      }
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

    async fetchScenarios(includeInactive = false): Promise<void> {
      this.scenariosLoading = true;
      this.scenariosError = null;
      try {
        this.scenarios = await api.listScenarios(includeInactive);
        this.scenariosIncludeInactive = includeInactive;
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
      const existing = this.scenarios[index];
      if (existing) {
        this.scenarios[index] = toSummary(updated, existing.session_count);
      }
      return updated;
    },

    // Imports one exported file. It overwrites a scenario that is already there, so the
    // list is re-read rather than patched: an import can both add and change a row.
    async importScenario(payload: unknown): Promise<ScenarioPayload> {
      const imported = await api.importScenario(payload);
      await this.fetchScenarios(this.scenariosIncludeInactive);
      return imported;
    },

    async retireScenario(scenarioId: string): Promise<void> {
      await api.retireScenario(scenarioId);
      await this.fetchScenarios(this.scenariosIncludeInactive);
    },

    async restoreScenario(scenarioId: string): Promise<void> {
      await api.restoreScenario(scenarioId);
      await this.fetchScenarios(this.scenariosIncludeInactive);
    },
  },
});
