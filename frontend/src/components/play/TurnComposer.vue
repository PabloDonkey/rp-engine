<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";

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
const activeIndex = ref(0);
const toggleEl = ref<HTMLButtonElement | null>(null);
const itemEls = ref<(HTMLButtonElement | null)[]>([]);

const canSend = computed(
  () => draft.value.trim().length > 0 && !props.generating && !props.disabled,
);

const items = computed(() => [
  {
    key: "continue" as const,
    // Two behaviours wore one name on Telegram. A button can afford to say which it is.
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

function openMenu(index = 0): void {
  if (props.disabled) return;
  menuOpen.value = true;
  activeIndex.value = index;
  void nextTick(() => itemEls.value[index]?.focus());
}

function closeMenu(returnFocus = true): void {
  menuOpen.value = false;
  if (returnFocus) void nextTick(() => toggleEl.value?.focus());
}

function moveActive(delta: number): void {
  const next = (activeIndex.value + delta + items.value.length) % items.value.length;
  activeIndex.value = next;
  itemEls.value[next]?.focus();
}

function activate(key: "continue" | "retry"): void {
  const item = items.value.find((candidate) => candidate.key === key);
  if (!item?.enabled) return;
  closeMenu(false);
  // The draft is deliberately untouched here. Neither action sends it.
  if (key === "continue") emit("continueStory");
  else emit("retry");
}

function onToggleKeydown(event: KeyboardEvent): void {
  if (event.key === "ArrowUp") {
    event.preventDefault();
    openMenu(items.value.length - 1);
  } else if (event.key === "ArrowDown") {
    event.preventDefault();
    openMenu(0);
  }
}

function onMenuKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") {
    event.preventDefault();
    closeMenu();
  } else if (event.key === "ArrowDown") {
    event.preventDefault();
    moveActive(1);
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    moveActive(-1);
  }
}

function onDocumentPointerDown(event: PointerEvent): void {
  const target = event.target as Node | null;
  if (!target) return;
  const root = toggleEl.value?.closest("[data-composer]");
  if (root && !root.contains(target)) closeMenu(false);
}

watch(menuOpen, (open) => {
  if (open) document.addEventListener("pointerdown", onDocumentPointerDown);
  else document.removeEventListener("pointerdown", onDocumentPointerDown);
});

onBeforeUnmount(() => document.removeEventListener("pointerdown", onDocumentPointerDown));
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
      <button
        ref="toggleEl"
        type="button"
        :disabled="disabled"
        aria-haspopup="menu"
        :aria-expanded="menuOpen"
        aria-label="More turn actions"
        class="rounded-r-md border border-l border-neutral-900 border-l-white/25 bg-neutral-900 px-2 py-2 text-xs text-white disabled:opacity-40 dark:border-white dark:border-l-black/20 dark:bg-white dark:text-neutral-900"
        @click="menuOpen ? closeMenu(false) : openMenu()"
        @keydown="onToggleKeydown"
      >
        ▾
      </button>

      <!-- Upward: this sits at the bottom of the screen, and on a phone the keyboard is
           under it. -->
      <div
        v-if="menuOpen"
        role="menu"
        class="absolute bottom-full right-0 z-10 mb-1 w-64 rounded-md border border-black/10 bg-white p-1 shadow-lg dark:border-white/10 dark:bg-neutral-900"
        @keydown="onMenuKeydown"
      >
        <button
          v-for="(item, index) in items"
          :key="item.key"
          :ref="(el) => (itemEls[index] = el as HTMLButtonElement | null)"
          type="button"
          role="menuitem"
          :disabled="!item.enabled"
          class="flex w-full items-baseline gap-2 rounded px-2 py-1.5 text-left text-sm enabled:hover:bg-black/5 disabled:text-neutral-400 dark:enabled:hover:bg-white/10"
          @click="activate(item.key)"
        >
          <span>{{ item.label }}</span>
          <span class="ml-auto text-right text-[11px] text-neutral-500">{{ item.hint }}</span>
        </button>
      </div>
    </div>
  </div>
</template>
