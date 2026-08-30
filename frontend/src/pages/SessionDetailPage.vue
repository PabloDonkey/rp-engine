<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import * as api from "@/api";
import SessionHeader from "@/components/play/SessionHeader.vue";
import SessionTranscript from "@/components/play/SessionTranscript.vue";
import TurnComposer from "@/components/play/TurnComposer.vue";
import { useAdminStore } from "@/stores/admin";

const props = defineProps<{ sessionId: string }>();
const store = useAdminStore();
const router = useRouter();

const transcriptRef = ref<InstanceType<typeof SessionTranscript> | null>(null);

async function load(): Promise<void> {
  await store.fetchSessionDetail(props.sessionId);
  // Open on the end of the story, not the beginning of it.
  await transcriptRef.value?.scrollToBottom();
}

onMounted(load);
watch(() => props.sessionId, load);

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

// --- Playing a turn (S031) ---

const draft = ref("");

const generating = computed(() => store.isGenerating);
const isRetired = computed(() => Boolean(store.session?.deleted_at));

const lastMessage = computed(() => store.transcript[store.transcript.length - 1] ?? null);

// Retry replaces a narrator reply, so there has to be one. The service refuses anything else
// and says why; this only decides whether to offer the item.
const canRetry = computed(() => lastMessage.value?.role === "character");

// The last reply stopped at the token cap, so Continue would finish that sentence in place
// rather than advance. Costs nothing to know: the finish reason is already on the message.
const finishesReply = computed(
  () =>
    lastMessage.value?.role === "character" &&
    lastMessage.value.metadata.finish_reason === "length",
);

async function onSend(message: string): Promise<void> {
  // The player just acted, so they are following by definition.
  await transcriptRef.value?.scrollToBottom();
  const ok = await store.playTurn(props.sessionId, message);
  // Only a send that worked clears the box. A refused turn leaves what was typed.
  if (ok) draft.value = "";
}

async function onContinue(): Promise<void> {
  await transcriptRef.value?.scrollToBottom();
  await store.playContinue(props.sessionId);
}

async function onRetry(): Promise<void> {
  await transcriptRef.value?.scrollToBottom();
  await store.playRetry(props.sessionId);
}
</script>

<template>
  <!-- `min-h-0` on a flex item overrides the default `min-height: auto`, which would
       otherwise refuse to shrink below the transcript's content height and defeat the
       fill-then-scroll layout below. Three sections, each its own component: header
       (title/meta/actions/tabs), transcript (scrolls on its own), composer (pinned). -->
  <div class="flex h-full min-h-0 flex-col">
    <RouterLink :to="backTo" class="shrink-0 text-body text-muted">&larr; Sessions</RouterLink>

    <p v-if="store.sessionLoading" class="mt-2 text-body text-muted">Loading…</p>
    <p v-else-if="store.sessionError" class="mt-2 text-body text-danger">
      {{ store.sessionError }}
    </p>

    <template v-else-if="store.session">
      <SessionHeader class="shrink-0" :session-id="sessionId" @export="onExport" @delete="onDelete" />

      <p
        v-if="store.actionError"
        class="mb-3 shrink-0 rounded-control border border-danger bg-danger-soft px-3 py-2 text-body text-danger"
      >
        {{ store.actionError }}
      </p>

      <SessionTranscript ref="transcriptRef" :session-id="sessionId" />

      <div class="mt-3 shrink-0">
        <TurnComposer
          v-model="draft"
          :generating="generating"
          :disabled="isRetired"
          :can-retry="canRetry"
          :finishes-reply="finishesReply"
          retry-reason="the last message is not a narrator reply"
          @send="onSend"
          @continue-story="onContinue"
          @retry="onRetry"
        />
      </div>
    </template>
  </div>
</template>
