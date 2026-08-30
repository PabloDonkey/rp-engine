<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { PMenu, type MenuItem } from "pablo-design-system";

/**
 * `[ Say or do something… · Send ▾ ]` — the composer for the session page.
 *
 * One bordered box holds the whole row: the text field is borderless and shares the box's
 * background, so Send and the field read as one control instead of two stacked ones. The
 * field grows with what you type, up to `MAX_HEIGHT_PX`, then scrolls internally instead of
 * growing the page — sizing is automatic, there is no drag handle.
 *
 * Send, Continue and Retry are three ways to do one thing: get the next reply. That is what
 * a split button is for, and it leaves the commands still on the bench somewhere to land
 * later without the composer growing each time.
 *
 * Four rules hold this together, and each one is a bug it would otherwise invite:
 *
 * 1. **The draft survives the menu.** Continue and Retry ignore the text box, so they must
 *    leave it alone. Only a send that succeeded clears it, and the parent decides that.
 * 2. **A blocked item is greyed with its reason, never hidden.** Hiding one changes the
 *    menu's height between openings, so the item being reached for moves under the finger.
 * 3. **Send stays Send.** Disabled while the box is empty, and it never becomes another
 *    action.
 * 4. **The buttons don't grow with the field.** They sit at the bottom of the row
 *    (`items-end`) at their own fixed height, the same way a chat app's send icon stays put
 *    while the field above it grows.
 */
const MAX_HEIGHT_PX = 160;

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

const textareaEl = ref<HTMLTextAreaElement | null>(null);

/** Grows the field to fit its content, capped at `MAX_HEIGHT_PX` where it scrolls instead. */
function autoGrow(): void {
  const el = textareaEl.value;
  if (!el) return;
  el.style.height = "auto";
  el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT_PX)}px`;
}

// Covers every way the draft can change from outside a keystroke: cleared after a send,
// restored from a different session, or set programmatically in a test.
watch(draft, () => nextTick(autoGrow));
onMounted(autoGrow);

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
  <!-- One box, one background: the border wraps the field and the buttons together, and
       the field itself is borderless, so the button reads as part of the writing area
       rather than a separate control glued on beside it. `focus-within` puts the focus
       ring on the shared box instead of the (border-less) field. -->
  <div
    data-composer
    class="flex items-end gap-1 rounded-control border border-hairline bg-surface p-1.5 focus-within:border-accent"
  >
    <textarea
      ref="textareaEl"
      v-model="draft"
      :disabled="generating || disabled"
      rows="1"
      class="min-h-[1.75rem] flex-1 resize-none border-0 bg-transparent px-1.5 py-1 text-body text-ink placeholder:text-faint focus:outline-none disabled:opacity-50"
      :style="{ maxHeight: `${MAX_HEIGHT_PX}px` }"
      :placeholder="disabled ? 'This story is retired.' : 'Say or do something…'"
      @input="autoGrow"
      @keydown.enter.exact.prevent="onSend"
    ></textarea>

    <!-- `shrink-0` and no height class: the row's `items-end` keeps this pinned to the
         bottom, but nothing here stretches when the field above it grows. -->
    <div class="flex shrink-0 items-center gap-0.5">
      <button
        type="button"
        :disabled="!canSend"
        class="rounded-control px-2.5 py-1 text-body font-medium text-accent enabled:hover:bg-accent-soft disabled:cursor-not-allowed disabled:text-faint"
        @click="onSend"
      >
        {{ generating ? "Writing…" : "Send" }}
      </button>

      <PMenu :items="items" @select="onSelect">
        <button
          type="button"
          :disabled="disabled"
          aria-label="More turn actions"
          class="rounded-control px-1.5 py-1 text-xs text-muted enabled:hover:bg-raised disabled:cursor-not-allowed disabled:text-faint"
        >
          ▾
        </button>
      </PMenu>
    </div>
  </div>
</template>
