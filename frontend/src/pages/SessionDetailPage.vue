<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";

import * as api from "@/api";
import type { AdminMessage, AdminTrace } from "@/api";
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

// Memory layers (ADR-026). Only the toggleable ones are listed: the recent conversation is
// the story itself, so there is no state to show for it.
const MEMORY_LAYERS: { id: string; label: string; hint: string }[] = [
  {
    id: "rolling_summary",
    label: "Rolling summary",
    hint: "Condenses what falls out of the recent window into a running recap.",
  },
];
function memoryEnabled(sourceId: string): boolean {
  return store.sessionMemory?.settings.enabled_sources.includes(sourceId) ?? false;
}

function onToggleMemory(sourceId: string): Promise<boolean> {
  return store.setSessionMemorySource(props.sessionId, sourceId, !memoryEnabled(sourceId));
}

function onRunSummary(): Promise<boolean> {
  return store.refreshSessionSummary(props.sessionId);
}

// What the last pass did, in a sentence. A pass that wrote nothing must not read like one
// that worked, which is the whole reason the outcome is reported at all.
const PASS_REPORT: Record<string, string> = {
  folded: "Recap updated with the turns that were waiting.",
  condensed: "The recap had outgrown its share, so it was shortened.",
  waiting_for_batch: "Nothing done — too few turns are waiting to be worth a model call.",
  up_to_date: "Nothing to do — the recap already covers everything past the fold line.",
  model_wrote_nothing:
    "The model returned no recap, so nothing changed. It spent its budget thinking. " +
    "Press again, or raise RP_ENGINE_MEMORY_SUMMARY_MAX_TOKENS.",
  nothing_to_do: "Nothing to do — this session has no story yet.",
};

const passReport = computed(() => {
  const outcome = store.sessionMemory?.last_pass;
  if (!outcome) return "";
  return PASS_REPORT[outcome] ?? outcome;
});

const passFailed = computed(() => store.sessionMemory?.last_pass === "model_wrote_nothing");

const memoryStatus = computed(() => store.sessionMemory?.status ?? null);

// The story, oldest first, as three shares of its turns: in the recap, waiting to be
// folded, and still replayed word for word. They always add up to the whole story.
const storyMap = computed(() => {
  const status = memoryStatus.value;
  if (!status || status.turns_total === 0) return null;
  const share = (turns: number) => (turns / status.turns_total) * 100;
  return {
    covered: { turns: status.covers_through_turn, percent: share(status.covers_through_turn) },
    pending: { turns: status.pending_turns, percent: share(status.pending_turns) },
    verbatim: { turns: status.verbatim_turns, percent: share(status.verbatim_turns) },
  };
});

// How full the next batch is. This fills and empties: folding a turn into the recap does
// not delete it, so the window itself never shrinks.
const foldPercent = computed(() =>
  memoryStatus.value ? Math.round(memoryStatus.value.fold_progress * 100) : 0,
);

// The recap against its own share of the budget. Over 100% means the pass will condense it.
const recapPercent = computed(() => {
  const status = memoryStatus.value;
  if (!status || status.summary_budget_tokens <= 0) return 0;
  return Math.round((status.summary_tokens / status.summary_budget_tokens) * 100);
});

const foldState = computed(() => {
  const status = memoryStatus.value;
  if (!status) return "";
  if (status.behind_turns > 0) {
    return `${status.behind_turns} turn(s) left the window uncovered — the next pass folds them at once`;
  }
  if (status.pending_turns === 0) {
    return "Nothing waiting. The recap covers everything past the fold line.";
  }
  if (status.fold_progress >= 1) {
    return `${status.pending_turns} turn(s) waiting — the next pass folds them`;
  }
  return `${status.pending_turns} turn(s) waiting, still under the batch the pass waits for`;
});

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

// Last-only deletion. A conversation is an ordered narrative: removing from the middle would
// leave replies answering messages that no longer exist, so undoing a bad stretch means
// peeling from the end. Turn 10 before turn 9.
function isLastMessage(index: number): boolean {
  return index === store.transcript.length - 1;
}

function messageLabel(message: AdminMessage): string {
  const turn = message.metadata.turn;
  return turn ? `turn ${turn}` : message.role;
}

async function onDeleteLastMessage(message: AdminMessage): Promise<void> {
  if (
    !confirm(
      `Delete the last message (${messageLabel(message)}) and its generation traces? ` +
        "This cannot be undone.",
    )
  ) {
    return;
  }
  // Indices shift when a message goes, so open debug filters would otherwise follow the
  // index onto a different message.
  for (const key of Object.keys(filterState)) delete filterState[Number(key)];
  await store.deleteLastMessage(props.sessionId);
}

// The operator exception to the set-once contract (ADR-025): a player can only change a
// persona with /clear, an admin can correct one in place. Superseded sessions are excluded
// because a persona there would never reach a prompt.
const personaDraft = reactive({ name: "", description: "" });
const personaSaving = ref(false);

const canEditPersona = computed(() => store.session !== null && !store.session.deleted_at);
const hasPersona = computed(() => Boolean(store.session?.user_persona_name));

// Keep the draft in step with whichever session is loaded, so the form opens on what is
// currently stored rather than on a stale edit.
watch(
  () => store.session,
  (session) => {
    personaDraft.name = session?.user_persona_name ?? "";
    personaDraft.description = session?.user_persona_description ?? "";
  },
  { immediate: true },
);

const personaDirty = computed(
  () =>
    personaDraft.name !== (store.session?.user_persona_name ?? "") ||
    personaDraft.description !== (store.session?.user_persona_description ?? ""),
);

async function onSavePersona(): Promise<void> {
  if (!personaDraft.name.trim()) return;
  // Renaming re-renders past turns under the new name — transcripts store `{{user}}`
  // unresolved — so the story stops matching what the player actually read.
  if (
    hasPersona.value &&
    personaDraft.name.trim() !== store.session?.user_persona_name &&
    !confirm(
      `Rename this player's character from "${store.session?.user_persona_name}" to ` +
        `"${personaDraft.name.trim()}"? Past turns will render under the new name, which ` +
        "will not match what the player already read.",
    )
  ) {
    return;
  }
  personaSaving.value = true;
  try {
    await store.setSessionPersona(props.sessionId, personaDraft.name, personaDraft.description);
  } finally {
    personaSaving.value = false;
  }
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
      <div class="mb-4 flex flex-wrap items-center gap-2 text-xs text-neutral-500">
        <span>{{ new Date(store.session.created_at).toLocaleString() }}</span>
        <span
          v-if="store.session.deleted_at"
          class="rounded border border-black/10 px-1.5 py-0.5 dark:border-white/10"
          :title="`Superseded ${new Date(store.session.deleted_at).toLocaleString()}`"
        >
          superseded
        </span>
      </div>

      <h2 class="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Player persona
      </h2>
      <div class="mb-6 rounded-lg border border-black/10 p-3 text-sm dark:border-white/10">
        <!-- Editable here, but only here: /clear is still the only way a *player* can change
             their character. An admin sees the whole session, so they can correct one. -->
        <form v-if="canEditPersona" class="grid gap-2" @submit.prevent="onSavePersona">
          <p v-if="!hasPersona" class="text-xs text-neutral-500">
            <!-- v-pre: the placeholder is literal text, not an interpolation. -->
            This session has no persona, so <code v-pre>{{user}}</code> falls back to the
            player's Telegram name.
          </p>
          <p v-else class="text-xs text-neutral-500">
            The player cannot change this themselves — /clear starts a fresh session instead.
            Renaming re-renders past turns under the new name.
          </p>
          <label class="grid gap-1">
            <span class="text-xs text-neutral-500">Name</span>
            <input
              v-model="personaDraft.name"
              type="text"
              maxlength="128"
              placeholder="Sera Vane"
              class="rounded-md border border-black/10 bg-transparent px-2 py-1.5 dark:border-white/10"
            />
          </label>
          <label class="grid gap-1">
            <span class="text-xs text-neutral-500">Description</span>
            <textarea
              v-model="personaDraft.description"
              rows="3"
              placeholder="A wary courier who trusts machines more than people. Loves rain, hates crowds."
              class="rounded-md border border-black/10 bg-transparent px-2 py-1.5 dark:border-white/10"
            ></textarea>
          </label>
          <div>
            <button
              type="submit"
              :disabled="!personaDraft.name.trim() || !personaDirty || personaSaving"
              class="rounded-md border border-black/10 px-3 py-1.5 text-sm font-medium disabled:opacity-40 dark:border-white/10"
            >
              {{ personaSaving ? "Saving…" : hasPersona ? "Update persona" : "Set persona" }}
            </button>
          </div>
        </form>

        <!-- Superseded: read-only. Nothing here would ever reach a prompt again. -->
        <dl v-else-if="hasPersona" class="grid gap-2">
          <div class="flex gap-2">
            <dt class="w-32 shrink-0 text-neutral-500">Name</dt>
            <dd>{{ store.session.user_persona_name }}</dd>
          </div>
          <div class="flex gap-2">
            <dt class="w-32 shrink-0 text-neutral-500">Description</dt>
            <dd>
              <span v-if="!store.session.user_persona_description" class="text-neutral-500">
                None
              </span>
              <span v-else class="whitespace-pre-wrap">
                {{ store.session.user_persona_description }}
              </span>
            </dd>
          </div>
          <p class="text-xs text-neutral-500">
            This session was superseded, so its persona is read-only.
          </p>
        </dl>

        <p v-else class="text-sm text-neutral-500">
          No persona, and this session was superseded — a persona set here would never reach
          a prompt.
        </p>
      </div>

      <h2 class="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Memory
      </h2>
      <div
        class="mb-6 grid gap-3 rounded-lg border border-black/10 p-3 text-sm dark:border-white/10"
      >
        <!-- The same switch the player has through /memory. -->
        <div v-for="layer in MEMORY_LAYERS" :key="layer.id" class="flex items-start gap-3">
          <button
            type="button"
            class="rounded border border-black/10 px-2 py-1 text-xs dark:border-white/10 disabled:opacity-50"
            :disabled="store.memoryBusy"
            @click="onToggleMemory(layer.id)"
          >
            {{ memoryEnabled(layer.id) ? "On" : "Off" }}
          </button>
          <div>
            <div>{{ layer.label }}</div>
            <div class="text-xs text-neutral-500">{{ layer.hint }}</div>
          </div>
        </div>

        <!-- The story, split the way memory splits it. The numbers are the ones the
             background worker itself uses. -->
        <div v-if="memoryStatus" class="grid gap-3 border-t border-black/10 pt-3 dark:border-white/10">
          <div v-if="storyMap" class="grid gap-1">
            <div class="flex flex-wrap items-baseline justify-between gap-2">
              <span class="text-xs uppercase tracking-wide text-neutral-500">
                The story, oldest first
              </span>
              <span class="font-mono text-xs tabular-nums">
                {{ memoryStatus.turns_total }} turns
              </span>
            </div>
            <div class="flex h-3 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
              <div
                class="h-full bg-teal-600"
                :style="{ width: `${storyMap.covered.percent}%` }"
                :title="`${storyMap.covered.turns} turn(s) in the recap`"
              ></div>
              <div
                class="h-full bg-amber-500"
                :style="{ width: `${storyMap.pending.percent}%` }"
                :title="`${storyMap.pending.turns} turn(s) waiting to be folded`"
              ></div>
              <div
                class="h-full bg-sky-600"
                :style="{ width: `${storyMap.verbatim.percent}%` }"
                :title="`${storyMap.verbatim.turns} turn(s) replayed word for word`"
              ></div>
            </div>
            <div class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-500">
              <span class="flex items-center gap-1.5">
                <span class="h-2 w-2 rounded-full bg-teal-600"></span>
                {{ storyMap.covered.turns }} in the recap
              </span>
              <span class="flex items-center gap-1.5">
                <span class="h-2 w-2 rounded-full bg-amber-500"></span>
                {{ storyMap.pending.turns }} waiting to fold
              </span>
              <span class="flex items-center gap-1.5">
                <span class="h-2 w-2 rounded-full bg-sky-600"></span>
                {{ storyMap.verbatim.turns }} word for word
              </span>
            </div>
            <div class="text-xs text-neutral-500">
              <template v-if="memoryStatus.whole_story_fits">
                Every stored turn still reaches the prompt. Folding does not delete anything —
                the recap is written ahead of the day the window has to drop them.
              </template>
              <template v-else>
                The window holds {{ memoryStatus.window_messages }} of
                {{ memoryStatus.stored_messages }} stored messages. The rest reach the model
                only through the recap.
              </template>
            </div>
          </div>

          <div class="grid gap-1">
            <div class="flex flex-wrap items-baseline justify-between gap-2">
              <span class="text-xs uppercase tracking-wide text-neutral-500">
                Next fold
              </span>
              <span class="font-mono text-xs tabular-nums">
                {{ memoryStatus.pending_tokens }} / {{ memoryStatus.fold_batch_tokens }} tokens
                ({{ foldPercent }}%)
              </span>
            </div>
            <div class="h-2 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
              <div
                class="h-full rounded-full transition-[width] duration-300"
                :class="
                  memoryStatus.behind_turns > 0
                    ? 'bg-amber-500'
                    : foldPercent >= 100
                      ? 'bg-emerald-600'
                      : 'bg-sky-600'
                "
                :style="{ width: `${Math.min(100, foldPercent)}%` }"
              ></div>
            </div>
            <div class="text-xs text-neutral-500">
              {{ foldState }} · window budget {{ memoryStatus.budget_tokens }} tokens, fold line
              at {{ memoryStatus.high_water_tokens }}
            </div>
          </div>

          <div class="grid gap-1">
            <div class="flex flex-wrap items-baseline justify-between gap-2">
              <span class="text-xs uppercase tracking-wide text-neutral-500">
                Recap against its share
              </span>
              <span class="font-mono text-xs tabular-nums">
                {{ memoryStatus.summary_tokens }} /
                {{ memoryStatus.summary_budget_tokens }} tokens ({{ recapPercent }}%)
              </span>
            </div>
            <div class="h-2 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
              <div
                class="h-full rounded-full transition-[width] duration-300"
                :class="recapPercent > 100 ? 'bg-amber-500' : 'bg-teal-600'"
                :style="{ width: `${Math.min(100, recapPercent)}%` }"
              ></div>
            </div>
            <div class="text-xs text-neutral-500">
              Covers turn {{ memoryStatus.covers_through_turn }} of
              {{ memoryStatus.turns_total }}. Over its share, the next pass condenses it.
            </div>
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2 border-t border-black/10 pt-3 dark:border-white/10">
          <button
            type="button"
            class="rounded border border-black/10 px-2 py-1 text-xs dark:border-white/10 disabled:opacity-50"
            :disabled="store.memoryBusy"
            @click="onRunSummary"
          >
            {{ store.memoryBusy ? "Running…" : "Run summary now" }}
          </button>
          <span class="text-xs text-neutral-500">
            Runs the same pass the background worker runs after a turn. It waits for the
            model, so on a reasoning model it can take a few minutes.
          </span>
        </div>

        <p
          v-if="passReport"
          class="text-xs"
          :class="passFailed ? 'text-amber-700 dark:text-amber-400' : 'text-neutral-500'"
        >
          {{ passReport }}
        </p>

        <div v-if="store.sessionMemory?.summary" class="grid gap-1">
          <div class="text-xs text-neutral-500">
            Story so far — covers {{ store.sessionMemory.summary.covers_through_turn }} turn(s),
            {{ store.sessionMemory.summary.tokens }} tokens, written by
            {{ store.sessionMemory.summary.model_name }} on
            {{ new Date(store.sessionMemory.summary.updated_at).toLocaleString() }}
          </div>
          <p class="whitespace-pre-wrap rounded border border-black/10 p-2 dark:border-white/10">
            {{ store.sessionMemory.summary.summary }}
          </p>
        </div>
        <p v-else class="text-xs text-neutral-500">
          No recap yet. It is written in the background, once the story passes the fold line.
        </p>
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
          <dt class="w-32 shrink-0 text-neutral-500">Director notes</dt>
          <dd>
            <span
              v-if="store.session.directives.director_instructions.length === 0"
              class="text-neutral-500"
            >
              None pending
            </span>
            <!-- Notes stack until a reply consumes them, so all queued ones show. -->
            <ul v-else class="flex flex-col gap-1">
              <li
                v-for="(note, index) in store.session.directives.director_instructions"
                :key="index"
                class="whitespace-pre-wrap"
              >
                <span class="text-neutral-500">{{ index + 1 }}.</span> {{ note }}
              </li>
            </ul>
          </dd>
        </div>
      </dl>

      <p
        v-if="store.actionError"
        class="mb-3 rounded-md border border-red-600/40 bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400"
      >
        {{ store.actionError }}
      </p>

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
            <!-- Only the final message is deletable, which is what enforces the ordering. -->
            <button
              v-if="isLastMessage(index)"
              type="button"
              class="ml-auto rounded border border-red-600/40 px-2 py-0.5 text-[11px] font-medium normal-case text-red-700 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-950/40"
              title="Delete this message. Only the last message can be deleted."
              @click="onDeleteLastMessage(message)"
            >
              Delete last
            </button>
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
