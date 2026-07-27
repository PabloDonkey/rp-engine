<script setup lang="ts">
import { computed, onMounted, reactive, watch } from "vue";
import { useRouter } from "vue-router";

import * as api from "@/api";
import type { AdminTrace } from "@/api";
import { useAdminStore } from "@/stores/admin";

const props = defineProps<{ sessionId: string }>();
const store = useAdminStore();
const router = useRouter();

interface MessageFilterState {
  thinking: boolean;
  trace: boolean;
  systemPrompt: boolean;
  turnMeta: boolean;
}

// Keyed by transcript index — each message's filter checkboxes are independent
// and don't carry over to any other message.
const filterState = reactive<Record<number, MessageFilterState>>({});

function filtersFor(index: number): MessageFilterState {
  let state = filterState[index];
  if (!state) {
    state = { thinking: false, trace: false, systemPrompt: false, turnMeta: false };
    filterState[index] = state;
  }
  return state;
}

function load(): void {
  store.fetchSessionDetail(props.sessionId);
}

onMounted(load);
watch(
  () => props.sessionId,
  () => {
    for (const key of Object.keys(filterState)) delete filterState[Number(key)];
    load();
  },
);

const backTo = computed(() =>
  store.session ? { name: "user-sessions", params: { userId: store.session.owner_id } } : "/users",
);

async function onDelete(): Promise<void> {
  if (!confirm("Delete this session? This clears its conversation too.")) return;
  await store.deleteSession(props.sessionId);
  router.push(backTo.value);
}

async function onExport(): Promise<void> {
  const exported = await api.exportSession(props.sessionId);
  const blob = new Blob([JSON.stringify(exported, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `session-${props.sessionId}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

function tracesForTurn(turn: string | undefined): AdminTrace[] {
  if (!turn) return [];
  return store.traces.filter((trace) => String(trace.record.turn ?? "") === turn);
}

function latestTraceForTurn(turn: string | undefined): AdminTrace | null {
  const matches = tracesForTurn(turn);
  return matches[matches.length - 1] ?? null;
}

function systemPromptFor(turn: string | undefined): string {
  const prompt = latestTraceForTurn(turn)?.record.prompt;
  if (prompt && typeof prompt === "object" && "assembled_system_prompt" in prompt) {
    return String((prompt as Record<string, unknown>).assembled_system_prompt ?? "");
  }
  return "";
}

function turnMetaFor(turn: string | undefined): Record<string, unknown> {
  const trace = latestTraceForTurn(turn);
  if (!trace) return {};
  return {
    finish_reason: trace.record.finish_reason,
    latency_ms: trace.record.latency_ms,
    usage: trace.record.usage,
  };
}
</script>

<template>
  <div>
    <RouterLink :to="backTo" class="text-sm text-neutral-500">&larr; Sessions</RouterLink>

    <p v-if="store.sessionLoading" class="mt-2 text-sm text-neutral-500">Loading…</p>
    <p v-else-if="store.sessionError" class="mt-2 text-sm text-red-600 dark:text-red-400">
      {{ store.sessionError }}
    </p>

    <template v-else-if="store.session">
      <div class="mt-1 flex items-start justify-between gap-3">
        <h1 class="text-xl font-semibold">{{ store.session.scenario_definition_id }}</h1>
        <div class="flex shrink-0 gap-2">
          <button
            type="button"
            class="rounded-md border border-black/10 px-3 py-1.5 text-sm font-medium dark:border-white/10"
            @click="onExport"
          >
            Export
          </button>
          <button
            type="button"
            class="rounded-md border border-red-600 px-3 py-1.5 text-sm font-medium text-red-700 dark:text-red-400"
            @click="onDelete"
          >
            Delete
          </button>
        </div>
      </div>
      <div class="mb-4 text-xs text-neutral-500">
        {{ new Date(store.session.created_at).toLocaleString() }}
      </div>

      <!-- Read-only: directives are set by the player over Telegram (/language, /rule,
           /director), the panel only reflects them. -->
      <h2 class="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Directives
      </h2>
      <dl
        class="mb-6 grid gap-2 rounded-lg border border-black/10 p-3 text-sm dark:border-white/10"
      >
        <div class="flex gap-2">
          <dt class="w-32 shrink-0 text-neutral-500">Language</dt>
          <dd>{{ store.session.directives.language }}</dd>
        </div>
        <div class="flex gap-2">
          <dt class="w-32 shrink-0 text-neutral-500">Scenario rules</dt>
          <dd>
            <span v-if="store.session.directives.rules.length === 0" class="text-neutral-500">
              None
            </span>
            <ul v-else class="flex flex-col gap-1">
              <li v-for="rule in store.session.directives.rules" :key="rule.id">
                <span class="text-neutral-500">{{ rule.id }}.</span> {{ rule.text }}
              </li>
            </ul>
          </dd>
        </div>
        <div class="flex gap-2">
          <dt class="w-32 shrink-0 text-neutral-500">Director note</dt>
          <dd>
            <span v-if="!store.session.directives.director_instruction" class="text-neutral-500">
              None pending
            </span>
            <span v-else class="whitespace-pre-wrap">
              {{ store.session.directives.director_instruction }}
            </span>
          </dd>
        </div>
      </dl>

      <h2 class="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Transcript
      </h2>
      <p v-if="store.transcript.length === 0" class="text-sm text-neutral-500">No messages yet.</p>
      <ol class="mb-6 flex flex-col gap-2">
        <li
          v-for="(message, index) in store.transcript"
          :key="index"
          class="rounded-lg border border-black/10 p-3 text-sm dark:border-white/10"
          :class="
            message.role === 'user'
              ? 'bg-blue-50 dark:bg-blue-950/40'
              : 'bg-white dark:bg-neutral-900'
          "
        >
          <div
            class="mb-1 flex items-center gap-2 text-xs font-semibold uppercase text-neutral-500"
          >
            <span>{{ message.role }}</span>
            <span v-if="message.metadata.turn">&middot; Turn {{ message.metadata.turn }}</span>
          </div>
          <div class="whitespace-pre-wrap">{{ message.content }}</div>

          <template v-if="message.role === 'character'">
            <div
              class="mt-2 flex flex-wrap gap-3 border-t border-black/5 pt-2 text-xs text-neutral-600 dark:border-white/5 dark:text-neutral-400"
            >
              <label
                class="flex items-center gap-1"
                :class="{ 'opacity-40': !message.metadata.thinking }"
              >
                <input
                  v-model="filtersFor(index).thinking"
                  type="checkbox"
                  :disabled="!message.metadata.thinking"
                />
                Thinking
              </label>
              <label class="flex items-center gap-1">
                <input v-model="filtersFor(index).trace" type="checkbox" />
                Raw trace
              </label>
              <label class="flex items-center gap-1">
                <input v-model="filtersFor(index).systemPrompt" type="checkbox" />
                System prompt
              </label>
              <label class="flex items-center gap-1">
                <input v-model="filtersFor(index).turnMeta" type="checkbox" />
                Turn metadata
              </label>
            </div>

            <div
              v-if="filtersFor(index).thinking"
              class="mt-2 overflow-x-auto whitespace-pre-wrap rounded-md bg-amber-50 p-2 text-xs dark:bg-amber-950/40"
            >
              {{ message.metadata.thinking }}
            </div>

            <div
              v-if="filtersFor(index).systemPrompt"
              class="mt-2 overflow-x-auto whitespace-pre-wrap rounded-md bg-neutral-50 p-2 text-xs dark:bg-neutral-800"
            >
              {{ systemPromptFor(message.metadata.turn) || "No system prompt recorded for this turn." }}
            </div>

            <div
              v-if="filtersFor(index).turnMeta"
              class="mt-2 overflow-x-auto rounded-md bg-neutral-50 p-2 text-xs dark:bg-neutral-800"
            >
              <pre>{{ JSON.stringify(turnMetaFor(message.metadata.turn), null, 2) }}</pre>
            </div>

            <div
              v-if="filtersFor(index).trace"
              class="mt-2 overflow-x-auto rounded-md bg-neutral-50 p-2 text-xs dark:bg-neutral-800"
            >
              <template v-if="tracesForTurn(message.metadata.turn).length > 0">
                <pre
                  v-for="(trace, traceIndex) in tracesForTurn(message.metadata.turn)"
                  :key="traceIndex"
                  >{{ JSON.stringify(trace.record, null, 2) }}</pre
                >
              </template>
              <span v-else class="text-neutral-500">No trace recorded for this turn.</span>
            </div>
          </template>
        </li>
      </ol>
    </template>
  </div>
</template>
