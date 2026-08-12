/**
 * What the retire dialog asks.
 *
 * It names the live session count before it asks, because retiring is invisible to the
 * people mid-story: they keep playing, and only `/play` stops working. Without the number,
 * "retire this?" reads like "end these stories?", which is not what it does.
 *
 * Shared by the list page and the detail page, so the two cannot drift into asking
 * different questions about the same action.
 */
export function retireMessage(name: string, sessionCount: number): string {
  const running =
    sessionCount === 0
      ? "No story is running it."
      : `${sessionCount} running ${sessionCount === 1 ? "story keeps" : "stories keep"} playing.`;
  return [
    `Retire "${name}"?`,
    "",
    running,
    "",
    "It leaves the catalog and /play stops offering it. Nothing is deleted, and you can restore it.",
  ].join("\n");
}
