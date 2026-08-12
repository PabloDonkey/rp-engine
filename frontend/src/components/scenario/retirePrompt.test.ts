import { expect, test } from "vitest";

import { retireMessage } from "@/components/scenario/retirePrompt";

test("names the live session count before it asks", () => {
  // Without the number, "retire this?" reads like "end these stories?", which it is not.
  const message = retireMessage("The Sealed Vault", 3);

  expect(message).toContain('Retire "The Sealed Vault"?');
  expect(message).toContain("3 running stories keep playing.");
});

test("uses the singular for one story", () => {
  expect(retireMessage("The Sealed Vault", 1)).toContain("1 running story keeps playing.");
});

test("says so when nobody is playing it", () => {
  expect(retireMessage("The Sealed Vault", 0)).toContain("No story is running it.");
});

test("says what retiring does not do", () => {
  // The whole point of a soft delete is that it is reversible, so the dialog must say so.
  const message = retireMessage("The Sealed Vault", 0);

  expect(message).toContain("Nothing is deleted");
  expect(message).toContain("restore it");
});
