<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch, watchEffect } from "vue";
import { PButton, PScrollArea } from "pablo-design-system";

import type { AdminMessage, AdminTrace } from "@/api";
import { useStickToBottom } from "@/composables/useStickToBottom";
import { useAdminStore } from "@/stores/admin";

/**
 * The story: past turns, the one in flight, and the "N new" pill when the reader has
 * scrolled away from the newest turn.
 *
 * Owns its own scroll container and exposes `scrollToBottom` — the parent calls it right
 * before dispatching a send/continue/retry, because "the player just acted" is the one
 * moment `useStickToBottom`'s measure-then-settle order requires from outside this
 * component.
 */
const props = defineProps<{ sessionId: string }>();
const store = useAdminStore();

interface MessageFilterState {
  thinking: boolean;
  trace: boolean;
  systemPrompt: boolean;
  turnMeta: boolean;
  // Whether the `···` control is open. It sits with the filters it reveals so that clearing
  // the state on a reload closes the menu too.
  menuOpen: boolean;
}

// Keyed by transcript index — each message's filter checkboxes are independent
// and don't carry over to any other message.
const filterState = reactive<Record<number, MessageFilterState>>({});

function filtersFor(index: number): MessageFilterState {
  let state = filterState[index];
  if (!state) {
    state = {
      thinking: false,
      trace: false,
      systemPrompt: false,
      turnMeta: false,
      menuOpen: false,
    };
    filterState[index] = state;
  }
  return state;
}

watch(
  () => props.sessionId,
  () => {
    for (const key of Object.keys(filterState)) delete filterState[Number(key)];
  },
);

const scrollAreaRef = ref<InstanceType<typeof PScrollArea> | null>(null);
// `PScrollArea`'s real scrolling element, not the ref itself: `useStickToBottom` wants a
// plain, writable `Ref<HTMLElement | null>`, and the exposed `viewport` only appears once
// Reka mounts its own viewport child, so this stays in step with that instead of capturing
// it once.
const transcriptEl = ref<HTMLElement | null>(null);
watchEffect(() => {
  transcriptEl.value = scrollAreaRef.value?.viewport ?? null;
});
const { unseen, measure, settle, scrollToBottom } = useStickToBottom(transcriptEl);

defineExpose({ scrollToBottom });

const pending = computed(() => store.pendingTurn);

// A new turn arrived. `sync` so this runs before the DOM is patched — the scroll position
// still describes the transcript as the reader last saw it, which is the only moment the
// "was I following?" question has a true answer.
watch(
  () => store.transcript.length,
  (next, previous) => {
    // `previous === 0` is the first load, which the page's own `scrollToBottom()` call
    // (after fetching) already handles. A shorter list is a delete, not a new turn.
    if (previous === 0 || next <= previous) return;
    void settle(measure());
  },
  { flush: "sync" },
);

// Last-only deletion. A conversation is an ordered narrative: removing from the middle would
// leave replies answering messages that no longer exist, so undoing a bad stretch means
// peeling from the end. Turn 10 before turn 9.
function isLastMessage(index: number): boolean {
  return index === store.transcript.length - 1;
}

/** What the reader calls each side. `user` / `character` are storage words, not reading ones. */
function roleLabel(message: AdminMessage): string {
  if (message.role === "user") return "you";
  if (message.role === "character") return "narrator";
  return message.role;
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

/** Whether this turn recorded anything the `···` could show.
 *
 * Turns written before S012/S022 carry no `turn` in their metadata, and the trace lookup is
 * by turn number — so for those the drawer opens onto four checkboxes that each answer
 * "nothing recorded". Say that on the control instead of behind it.
 */
function hasThinking(message: AdminMessage): boolean {
  return Boolean(message.metadata.thinking);
}

function hasTrace(message: AdminMessage): boolean {
  return tracesForTurn(message.metadata.turn).length > 0;
}

function hasSystemPrompt(message: AdminMessage): boolean {
  return systemPromptFor(message.metadata.turn) !== "";
}

function hasAnyDebug(message: AdminMessage): boolean {
  return hasThinking(message) || hasTrace(message);
}

function debugOpen(index: number): boolean {
  return filtersFor(index).menuOpen;
}

async function toggleDebug(index: number, event: MouseEvent): Promise<void> {
  const state = filtersFor(index);
  state.menuOpen = !state.menuOpen;
  if (!state.menuOpen) return;
  // The row opens *below* the message, and the message is usually the last one in a short
  // scroll box — so the thing that just appeared is off-screen and the click reads as doing
  // nothing. Bring it back into view once it exists.
  await nextTick();
  // Target the revealed row, not the message. A long narrator turn is taller than the scroll
  // box, so the browser already counts the `li` as "in view" and `nearest` moves nothing —
  // which is exactly the bug: the options open 500px below the fold and the click looks dead.
  const row = (event.currentTarget as HTMLElement | null)
    ?.closest("li")
    ?.querySelector("[data-debug-row]");
  row?.scrollIntoView({ block: "nearest", behavior: "smooth" });
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
  <div class="relative min-h-0 flex-1">
    <!-- The scroll well's tint is deliberately not a token: it's a recessed area, not a
         surface or a panel, and no token in the package models "recessed" (S032 audit).
         Height comes from the parent's flex layout, not a `calc()` guess: this fills
         whatever the header/composer leave behind, down to the true bottom of the
         viewport, instead of leaving dead space under the composer. `data-testid` lands on
         `PScrollArea`'s viewport, not its root -- the root's own height is pinned to its
         child, so it never actually overflows, and a test (or a screen reader) asking
         "is this the thing that scrolls" needs the viewport. -->
    <PScrollArea
      ref="scrollAreaRef"
      data-testid="transcript-scroll"
      class="h-full min-h-[15rem] rounded-panel border border-hairline-soft bg-ground"
      viewport-class="px-3 py-3"
    >
      <p v-if="store.transcript.length === 0 && !pending" class="p-2 text-body text-muted">
        No messages yet.
      </p>
      <ol class="flex flex-col gap-5">
        <li
          v-for="(message, index) in store.transcript"
          :key="index"
          class="group rounded-control px-4 py-3"
          :class="
            message.role === 'user'
              ? 'ml-3 bg-accent-soft sm:ml-6'
              : 'mr-3 border border-hairline-soft bg-surface sm:mr-6'
          "
        >
          <div
            class="mb-1.5 flex items-center gap-2 text-micro font-semibold uppercase tracking-wider text-muted"
          >
            <span>{{ roleLabel(message) }}</span>
            <span v-if="message.metadata.turn">&middot; turn {{ message.metadata.turn }}</span>
            <span class="ml-auto flex items-center gap-2 normal-case">
              <!-- Only the final message is deletable, which is what enforces the ordering. -->
              <PButton
                v-if="isLastMessage(index)"
                variant="danger"
                size="sm"
                title="Delete this message. Only the last message can be deleted."
                @click="onDeleteLastMessage(message)"
              >
                Delete last
              </PButton>
            </span>
          </div>
          <div
            class="whitespace-pre-wrap text-prose"
            :class="message.role === 'character' ? 'font-display' : ''"
          >
            {{ message.content }}
          </div>

          <template v-if="message.role === 'character'">
            <!-- Named, and placed where its content will appear. A `···` in the header was
                 two guesses: what it does, and where the answer will show up. -->
            <button
              type="button"
              :disabled="!hasAnyDebug(message)"
              class="mt-3 -mb-1 flex items-center gap-1.5 rounded text-micro font-medium uppercase tracking-wider text-muted enabled:hover:text-ink disabled:cursor-default disabled:opacity-60"
              :aria-expanded="debugOpen(index)"
              @click="toggleDebug(index, $event)"
            >
              <span aria-hidden="true" class="text-[9px]">{{ debugOpen(index) ? "▾" : "▸" }}</span>
              <span v-if="!hasAnyDebug(message)">No admin data for this turn</span>
              <span v-else>{{ debugOpen(index) ? "Hide" : "Show" }} admin actions</span>
            </button>

            <div
              v-if="debugOpen(index)"
              data-debug-row
              class="mt-2 flex scroll-mb-24 flex-wrap gap-3 border-t border-hairline pt-2 text-micro text-muted"
            >
              <label
                class="flex items-center gap-1"
                :class="{ 'opacity-40': !hasThinking(message) }"
                :title="hasThinking(message) ? '' : 'No thinking captured for this turn.'"
              >
                <input
                  v-model="filtersFor(index).thinking"
                  type="checkbox"
                  :disabled="!hasThinking(message)"
                />
                Thinking
              </label>
              <label
                class="flex items-center gap-1"
                :class="{ 'opacity-40': !hasTrace(message) }"
                :title="hasTrace(message) ? '' : 'No trace recorded for this turn.'"
              >
                <input
                  v-model="filtersFor(index).trace"
                  type="checkbox"
                  :disabled="!hasTrace(message)"
                />
                Raw trace
              </label>
              <label
                class="flex items-center gap-1"
                :class="{ 'opacity-40': !hasSystemPrompt(message) }"
                :title="hasSystemPrompt(message) ? '' : 'No system prompt recorded for this turn.'"
              >
                <input
                  v-model="filtersFor(index).systemPrompt"
                  type="checkbox"
                  :disabled="!hasSystemPrompt(message)"
                />
                System prompt
              </label>
              <label
                class="flex items-center gap-1"
                :class="{ 'opacity-40': !hasTrace(message) }"
                :title="hasTrace(message) ? '' : 'No trace recorded for this turn.'"
              >
                <input
                  v-model="filtersFor(index).turnMeta"
                  type="checkbox"
                  :disabled="!hasTrace(message)"
                />
                Turn metadata
              </label>
            </div>

            <div
              v-if="filtersFor(index).thinking"
              class="mt-2 overflow-x-auto whitespace-pre-wrap rounded-control bg-warning-soft p-2 text-micro"
            >
              {{ message.metadata.thinking }}
            </div>

            <div
              v-if="filtersFor(index).systemPrompt"
              class="mt-2 overflow-x-auto whitespace-pre-wrap rounded-control bg-raised p-2 text-micro"
            >
              {{ systemPromptFor(message.metadata.turn) || "No system prompt recorded for this turn." }}
            </div>

            <div
              v-if="filtersFor(index).turnMeta"
              class="mt-2 overflow-x-auto rounded-control bg-raised p-2 text-micro"
            >
              <pre>{{ JSON.stringify(turnMetaFor(message.metadata.turn), null, 2) }}</pre>
            </div>

            <div
              v-if="filtersFor(index).trace"
              class="mt-2 overflow-x-auto rounded-control bg-raised p-2 text-micro"
            >
              <template v-if="tracesForTurn(message.metadata.turn).length > 0">
                <pre
                  v-for="(trace, traceIndex) in tracesForTurn(message.metadata.turn)"
                  :key="traceIndex"
                  >{{ JSON.stringify(trace.record, null, 2) }}</pre
                >
              </template>
              <span v-else class="text-muted">No trace recorded for this turn.</span>
            </div>
          </template>
        </li>
      </ol>

      <!-- The turn in flight. It is drawn here rather than pushed into `transcript`,
           which stays the server's list and nothing else. -->
      <div v-if="pending" class="mt-5 flex flex-col gap-5">
        <!-- Bubble tint matches the mockup: the accent-soft "you" tint and the plain
             surface/hairline narrator bubble, same as the transcript above. -->
        <div v-if="pending.message" class="ml-3 rounded-control bg-accent-soft px-4 py-3 sm:ml-6">
          <div class="mb-1.5 text-micro font-semibold uppercase tracking-wider text-muted">
            you
          </div>
          <div class="whitespace-pre-wrap text-prose">
            {{ pending.message }}
          </div>
        </div>
        <div
          class="mr-3 rounded-control px-4 py-3 sm:mr-6"
          :class="pending.error ? 'bg-danger-soft' : 'border border-hairline-soft bg-surface'"
        >
          <template v-if="pending.error">
            <div class="mb-1.5 text-micro font-semibold uppercase tracking-wider text-danger">
              not sent
            </div>
            <div class="text-prose text-danger">
              {{ pending.error }}
            </div>
            <PButton size="sm" class="mt-2" @click="store.clearPendingTurn()">
              Dismiss
            </PButton>
          </template>
          <template v-else>
            <div class="mb-1.5 text-micro font-semibold uppercase tracking-wider text-muted">
              narrator
            </div>
            <div class="flex items-center gap-2 font-display text-prose italic text-muted">
              <span class="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-muted"></span>
              writing…
            </div>
          </template>
        </div>
      </div>
    </PScrollArea>

    <!-- Only while the reader is away from the newest turn. Following, there is nothing
         to jump to. Not PButton: this wants an inverted-contrast floating affordance
         (dark pill on light, light pill on dark), which `bg-ink`/`text-ground` gives for
         free -- both tokens already flip per theme, mirroring the mockup's pill exactly. -->
    <div v-if="unseen > 0" class="pointer-events-none absolute inset-x-0 bottom-2 flex justify-center">
      <button
        type="button"
        class="pointer-events-auto rounded-full bg-ink px-3 py-1 text-micro font-medium text-ground shadow-lg"
        @click="scrollToBottom(true)"
      >
        &darr; {{ unseen }} new
      </button>
    </div>
  </div>
</template>
