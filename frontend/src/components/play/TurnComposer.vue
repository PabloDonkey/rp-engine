<script setup lang="ts">
import { computed, ref } from "vue";
import {
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuPortal,
  DropdownMenuRoot,
  DropdownMenuTrigger,
} from "reka-ui";

/**
 * `[ Send ▾ ]` — the composer for the session page.
 *
 * Send, Continue and Retry are three ways to do one thing: get the next reply. That is what
 * a split button is for, and it leaves the commands still on the bench somewhere to land
 * later without the composer growing each time.
 *
 * Three rules hold this together, and each one is a bug it would otherwise invite:
 *
 * 1. **The draft survives the menu.** Continue and Retry ignore the text box, so they must
 *    leave it alone. Only a send that succeeded clears it, and the parent decides that.
 * 2. **A blocked item is greyed with its reason, never hidden.** Hiding one changes the
 *    menu's height between openings, so the item being reached for moves under the finger.
 * 3. **Send stays Send.** Disabled while the box is empty, and it never becomes another
 *    action.
 */
const props = defineProps<{
  /** A turn is running. Everything is disabled and Send reads as busy. */
  generating: boolean;
  /** The story is retired or otherwise closed to new turns. */
  disabled?: boolean;
  /** The last stored message is a narrator reply, which is what Retry needs. */
  canRetry: boolean;
  /** Why Retry is unavailable. Shown beside the greyed item. */
  retryReason?: string;
  /** The last reply stopped at the token limit, so Continue would finish it in place. */
  finishesReply: boolean;
}>();

const emit = defineEmits<{
  send: [message: string];
  continueStory: [];
  retry: [];
}>();

const draft = defineModel<string>({ default: "" });

const menuOpen = ref(false);

const canSend = computed(
  () => draft.value.trim().length > 0 && !props.generating && !props.disabled,
);

const items = computed(() => [
  {
    key: "continue" as const,
    label: props.finishesReply ? "Finish reply" : "Continue",
    hint: props.finishesReply ? "the last reply was cut off" : "advance with no input",
    enabled: !props.generating && !props.disabled,
  },
  {
    key: "retry" as const,
    label: "Retry",
    hint: props.canRetry
      ? "drop the last reply and roll again"
      : (props.retryReason ?? "the last message is not a narrator reply"),
    enabled: props.canRetry && !props.generating && !props.disabled,
  },
]);

function onSend(): void {
  if (!canSend.value) return;
  emit("send", draft.value.trim());
}

function activate(key: "continue" | "retry"): void {
  const item = items.value.find((candidate) => candidate.key === key);
  if (!item?.enabled) return;
  menuOpen.value = false;
  // The draft is deliberately untouched here. Neither action sends it.
  if (key === "continue") emit("continueStory");
  else emit("retry");
}
</script>

<template>
  <div data-composer class="relative flex items-end gap-2">
    <textarea
      v-model="draft"
      :disabled="generating || disabled"
      rows="2"
      class="min-h-[2.75rem] flex-1 resize-y rounded-md border border-black/10 bg-white px-2.5 py-2 text-sm disabled:opacity-50 dark:border-white/10 dark:bg-neutral-900"
      :placeholder="disabled ? 'This story is retired.' : 'Say or do something…'"
      @keydown.enter.exact.prevent="onSend"
    ></textarea>

    <div class="relative flex shrink-0">
      <button
        type="button"
        :disabled="!canSend"
        class="rounded-l-md border border-neutral-900 bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40 dark:border-white dark:bg-white dark:text-neutral-900"
        @click="onSend"
      >
        {{ generating ? "Writing…" : "Send" }}
      </button>

      <DropdownMenuRoot :open="menuOpen" @update:open="(open) => (menuOpen = open)">
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            :disabled="disabled"
            aria-label="More turn actions"
            aria-haspopup="menu"
            :aria-expanded="menuOpen"
            class="rounded-r-md border border-l border-neutral-900 border-l-white/25 bg-neutral-900 px-2 py-2 text-xs text-white disabled:opacity-40 dark:border-white dark:border-l-black/20 dark:bg-white dark:text-neutral-900"
          >
            ▾
          </button>
        </DropdownMenuTrigger>

        <DropdownMenuPortal>
          <DropdownMenuContent
            class="z-50 min-w-48 rounded-md border border-black/10 bg-white p-1 shadow-lg dark:border-white/10 dark:bg-neutral-900"
            :side-offset="8"
          >
            <template v-for="item in items" :key="item.key">
              <DropdownMenuItem
                :disabled="!item.enabled"
                class="flex w-full items-baseline gap-2 rounded px-2 py-1.5 text-left text-sm enabled:hover:bg-black/5 disabled:text-neutral-400 dark:enabled:hover:bg-white/10"
                @select="activate(item.key)"
              >
                <span>{{ item.label }}</span>
                <span class="ml-auto text-right text-[11px] text-neutral-500">{{ item.hint }}</span>
              </DropdownMenuItem>
            </template>
          </DropdownMenuContent>
        </DropdownMenuPortal>
      </DropdownMenuRoot>
    </div>
  </div>
</template>
