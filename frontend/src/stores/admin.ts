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

/** What the panel asked the story to do, while it is still asking.
 *
 * This rides *beside* `transcript` rather than inside it. `transcript` is the server's list
 * and everything that reads it — the delete-last button, the per-turn trace lookup — treats
 * every entry as real and stored. Slipping a not-yet-real row in means teaching all of them
 * to tell the difference, which is a worse trade than one extra field.
 */
export type PendingTurn = {
  action: "turn" | "continue" | "retry";
  /** What the player typed. Null for continue and retry, which send no text. */
  message: string | null;
  /** Set when the turn came back refused or failed. The typed text stays on screen with it. */
  error: string | null;
};

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
    // The turn in flight, or the one that just failed. Null when the story is idle.
    pendingTurn: null as PendingTurn | null,
    sessionLoading: false,
    sessionError: null as string | null,

    scenarios: [] as ScenarioSummary[],
    scenariosLoading: false,
    scenariosError: null as string | null,
    // Whether the list on screen includes retired scenarios. Off by default, and kept in
    // state so a retire or restore can re-read the list the operator is actually looking at.
    scenariosIncludeInactive: false,

    scenario: null as ScenarioPayload | null,
    // The list row for the open scenario. It carries the two facts the transfer payload
    // deliberately leaves out: whether the scenario is retired, and how many stories run it.
    scenarioSummary: null as ScenarioSummary | null,
    scenarioLoading: false,
    scenarioError: null as string | null,
  }),
  getters: {
    /** A turn is in flight. A pending row that carries an error is finished, not running. */
    isGenerating(state): boolean {
      return state.pendingTurn !== null && state.pendingTurn.error === null;
    },
  },
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
        // Two reads: the definition itself, and the list row for the lifecycle and the live
        // session count. `deleted_at` is not in the definition payload on purpose — that is
        // a transfer format, and it describes a scenario, not its life in one database.
        // Asking for retired rows too, or a retired scenario would have no row at all.
        const [scenario, rows] = await Promise.all([
          api.getScenario(scenarioId),
          api.listScenarios(true),
        ]);
        this.scenario = scenario;
        this.scenarioSummary = rows.find((row) => row.id === scenarioId) ?? null;
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
      await this.refreshAfterLifecycleChange(scenarioId);
    },

    async restoreScenario(scenarioId: string): Promise<void> {
      await api.restoreScenario(scenarioId);
      await this.refreshAfterLifecycleChange(scenarioId);
    },

    // Retire and restore answer 204, so the new state has to be read back. Both the list
    // and the open detail page show the lifecycle, so both are refreshed.
    async refreshAfterLifecycleChange(scenarioId: string): Promise<void> {
      await this.fetchScenarios(this.scenariosIncludeInactive);
      if (this.scenario?.id === scenarioId) {
        await this.fetchScenario(scenarioId);
      }
    },

    // --- Playing a turn (S031) ---

    async playTurn(sessionId: string, message: string): Promise<boolean> {
      return this.runTurn(sessionId, "turn", message, () => api.sendTurn(sessionId, message));
    },

    async playContinue(sessionId: string): Promise<boolean> {
      return this.runTurn(sessionId, "continue", null, () => api.continueStory(sessionId));
    },

    async playRetry(sessionId: string): Promise<boolean> {
      return this.runTurn(sessionId, "retry", null, () => api.retryTurn(sessionId));
    },

    /** One turn, start to finish.
     *
     * The pending row is set before the request goes out, which is the whole point: a reply
     * takes tens of seconds and a page with no visible pending state reads as broken.
     *
     * On success the session is re-read rather than the reply appended. The server is the
     * authority on what the transcript now holds — Retry in particular *replaces* a message
     * rather than adding one — and the same read refreshes the memory bars and the traces
     * the new turn produced.
     */
    async runTurn(
      sessionId: string,
      action: PendingTurn["action"],
      message: string | null,
      run: () => Promise<unknown>,
    ): Promise<boolean> {
      if (this.isGenerating) {
        return false;
      }
      this.actionError = null;
      this.pendingTurn = { action, message, error: null };
      try {
        await run();
        // Cleared only once the refetched transcript is in. Clearing it first drops
        // `isGenerating` while the old transcript is still on screen, which re-enables Send
        // and lets a second turn go out against a story the operator cannot see yet.
        await this.fetchSessionDetail(sessionId);
        this.pendingTurn = null;
        return true;
      } catch (error) {
        // Keep the pending row and put the reason in it. The typed text lives there, so
        // failing this way is what stops a refused turn eating what the player wrote.
        this.pendingTurn = {
          action,
          message,
          error: error instanceof Error ? error.message : String(error),
        };
        return false;
      }
    },

    /** Drop a failed turn: the player has read the reason, or is retyping. */
    clearPendingTurn(): void {
      this.pendingTurn = null;
    },
  },
});
