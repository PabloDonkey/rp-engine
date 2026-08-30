<script setup lang="ts">
import { computed } from "vue";
import { PMenu, type MenuItem } from "pablo-design-system";

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

const canSend = computed(
  () => draft.value.trim().length > 0 && !props.generating && !props.disabled,
);

const items = computed<MenuItem[]>(() => [
  {
    label: props.finishesReply ? "Finish reply" : "Continue",
    value: "continue",
    hint: props.finishesReply ? "the last reply was cut off" : "advance with no input",
    disabled: props.generating || props.disabled,
  },
  {
    label: "Retry",
    value: "retry",
    hint: props.canRetry ? "drop the last reply and roll again" : undefined,
    disabledReason: !props.canRetry
      ? (props.retryReason ?? "the last message is not a narrator reply")
      : undefined,
    disabled: props.generating || props.disabled,
  },
]);

function onSend(): void {
  if (!canSend.value) return;
  emit("send", draft.value.trim());
}

function onSelect(value: string): void {
  // The draft is deliberately untouched here. Neither action sends it.
  if (value === "continue") emit("continueStory");
  else if (value === "retry") emit("retry");
}
</script>

<template>
  <div data-composer class="flex items-end gap-2">
    <textarea
      v-model="draft"
      :disabled="generating || disabled"
      rows="1"
      class="min-h-[2.5rem] flex-1 resize-y rounded-control border border-hairline bg-surface px-2.5 py-2 text-body text-ink placeholder:text-faint disabled:opacity-50"
      :placeholder="disabled ? 'This story is retired.' : 'Say or do something…'"
      @keydown.enter.exact.prevent="onSend"
    ></textarea>

    <div class="flex h-10 shrink-0">
      <button
        type="button"
        :disabled="!canSend"
        class="rounded-l-control border border-accent bg-accent px-4 text-body font-medium text-accent-contrast disabled:cursor-not-allowed disabled:opacity-50"
        @click="onSend"
      >
        {{ generating ? "Writing…" : "Send" }}
      </button>

      <PMenu :items="items" @select="onSelect">
        <button
          type="button"
          :disabled="disabled"
          aria-label="More turn actions"
          class="h-full rounded-r-control border border-l border-accent border-l-accent-contrast/25 bg-accent px-2 text-xs text-accent-contrast disabled:cursor-not-allowed disabled:opacity-50"
        >
          ▾
        </button>
      </PMenu>
    </div>
  </div>
</template>
