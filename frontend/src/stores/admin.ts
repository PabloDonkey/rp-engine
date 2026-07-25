import { defineStore } from "pinia";

import * as api from "@/api";
import type { AdminMessage, AdminSession, AdminTrace, AdminUser } from "@/api";

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

    async toggleBlock(user: AdminUser): Promise<void> {
      const updated = user.is_blocked
        ? await api.unblockUser(user.id)
        : await api.blockUser(user.id);
      const index = this.users.findIndex((u) => u.id === user.id);
      if (index !== -1) {
        this.users[index] = updated;
      }
    },
  },
});
