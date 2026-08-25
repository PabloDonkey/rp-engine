import { nextTick, onBeforeUnmount, ref, watch, type Ref } from "vue";

/** How near the bottom still counts as following along. Roughly one line of story. */
export const NEAR_BOTTOM_PX = 96;

/**
 * Follow the newest turn, unless the reader has scrolled away from it.
 *
 * The whole behaviour hangs on one question — is the container within `NEAR_BOTTOM_PX` of
 * the bottom — and on asking it at the right moment. `measure()` must be called *before* new
 * content is added and `settle()` after, because content that has already landed is exactly
 * what pushes the view away from the bottom: measured afterwards the answer is always "no",
 * and the view would never follow anything.
 */
export function useStickToBottom(container: Ref<HTMLElement | null>) {
  const following = ref(true);
  const unseen = ref(0);

  function distanceFromBottom(el: HTMLElement): number {
    return el.scrollHeight - el.scrollTop - el.clientHeight;
  }

  function isNearBottom(): boolean {
    const el = container.value;
    // No container yet means nothing has scrolled away, so following is the honest answer.
    return el ? distanceFromBottom(el) <= NEAR_BOTTOM_PX : true;
  }

  function onScroll(): void {
    following.value = isNearBottom();
    if (following.value) unseen.value = 0;
  }

  /** Read the position before content changes. Pass the result to `settle`. */
  function measure(): boolean {
    following.value = isNearBottom();
    return following.value;
  }

  /** Act on what `measure` saw: follow along, or count what the reader has not seen. */
  async function settle(wasFollowing: boolean): Promise<void> {
    if (wasFollowing) {
      await scrollToBottom();
      return;
    }
    unseen.value += 1;
  }

  async function scrollToBottom(smooth = false): Promise<void> {
    // Wait for the new rows to exist, or `scrollHeight` is still the old height.
    await nextTick();
    const el = container.value;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? "smooth" : "auto" });
    following.value = true;
    unseen.value = 0;
  }

  // The container lives inside a `v-if`, so it appears and disappears. Track it rather than
  // binding once on mount, when it is still null.
  let attached: HTMLElement | null = null;
  watch(
    container,
    (el) => {
      if (attached) attached.removeEventListener("scroll", onScroll);
      attached = el;
      if (el) el.addEventListener("scroll", onScroll, { passive: true });
    },
    { immediate: true },
  );
  onBeforeUnmount(() => {
    if (attached) attached.removeEventListener("scroll", onScroll);
  });

  return { following, unseen, measure, settle, scrollToBottom };
}
