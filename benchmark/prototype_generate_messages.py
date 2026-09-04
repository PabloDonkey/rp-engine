"""PROTOTYPE — throwaway, not production code.

Phase 1 of 2. Generates the player lines for every scenario category (see
`prototype_lore_relevance_fixture.SCENARIO_SPECS`) and writes them to
`prototype_generated_messages.jsonl` for review before the slower, Postgres-backed test
phase in `prototype_lore_relevance_check.py` consumes them.

Rotates one local model per category (`prototype_lore_relevance_fixture.MODEL_ROTATION`),
so the 60 generated lines aren't all in one model's voice. Work is grouped by model, not
by category order: every category assigned to a given model runs to completion before the
next model is loaded, so no model is ever loaded more than once regardless of how many
categories point at it. Every rotation candidate was checked with `lms load
--estimate-only` to confirm it loads at 100% GPU offload on this machine - the point of
restricting to those is speed (no CPU-offload spillover slows generation down, no
reload thrash), not model choice.

Generates through `prototype_lore_relevance_fixture.generate_no_thinking_with_retry`
(LM Studio's native REST API with `reasoning: "off"` where the model supports it), not
through `LMStudioProvider`/the SDK - a one-line message is not a task reasoning helps
with, and for the reasoning-capable models in the rotation, letting them think first was
the direct cause of the empty-reply failures this script hit earlier (a full token budget
spent thinking, nothing left for the actual line). Confirmed directly: with reasoning on,
gemma-4-26b-a4b-it-heretic spent 1000+ characters thinking on a trivial prompt; with it
off, `reasoning_output_tokens: 0` and the reply arrived in ~0.2s.

Within a category, each repeat also gets a randomized delivery-style hint
(`prototype_lore_relevance_fixture.STYLE_HINTS`) and is told which lines this category has
already produced - including lines already saved to disk from an earlier run of this same
category, not just ones generated in the current process - with an instruction not to
repeat their wording or structure. This history is strictly per-category: a
`false_positive` call never sees `near_miss` lines or vice versa. Without this, a narrow
spec reliably collapsed to near-duplicate lines even across repeats - observed directly on
the first run (8/8 false_positive lines were minor rewordings of "the smell of burning
coal is strong in here").

Each line is written and flushed to disk immediately after it is generated, not batched
until the end - a crash or interrupt partway through a ~60-call run loses nothing already
generated. Appends to the output file rather than overwriting it, so re-running this
script adds to what is already there instead of discarding it.

No Postgres, no ConversationBuilder here - just the local model turning each category's
abstract spec into concrete wording, `REPEATS_PER_SCENARIO` times per category.

Run: uv run python benchmark/prototype_generate_messages.py
Output: benchmark/prototype_generated_messages.jsonl (one
{"category", "message", "model", "temperature", "max_tokens"} record per line, appended
as generated) plus the same lines printed to stdout.
"""

import asyncio
import json
import random
from typing import IO

from prototype_lore_relevance_fixture import (
    GENERATED_MESSAGES_PATH,
    MODEL_ROTATION,
    PLAYER_LINE_MAX_TOKENS,
    REPEATS_PER_SCENARIO,
    SCENARIO_SPECS,
    STYLE_HINTS,
    generate_no_thinking_with_retry,
    switch_model,
)

TEMPERATURE = 0.8


def _build_prompt(spec: str, previous: list[str]) -> str:
    parts = [spec, random.choice(STYLE_HINTS)]
    if previous:
        avoid = "\n".join(f"- {line}" for line in previous)
        parts.append(
            "You have already written these lines for this same task. Do not reuse their "
            f"wording, sentence structure, or specific details - write something "
            f"meaningfully different this time:\n{avoid}"
        )
    parts.append("Write the line now.")
    return "\n\n".join(parts)


def _existing_messages_by_category() -> dict[str, list[str]]:
    """Group already-saved messages by category, so a repeat run seeds the anti-repeat
    context from what is already on disk for that category, not just from lines generated
    in the current process. Never reads across categories - a `false_positive` run must
    never see `near_miss` lines and vice versa."""
    if not GENERATED_MESSAGES_PATH.exists():
        return {}
    grouped: dict[str, list[str]] = {}
    with GENERATED_MESSAGES_PATH.open() as f:
        for line in f:
            # Tolerate blank lines / stray whitespace - this file gets hand-edited.
            if not line.strip():
                continue
            record = json.loads(line)
            grouped.setdefault(record["category"], []).append(record["message"])
    return grouped


async def _generate_and_save(
    category: str,
    spec: str,
    *,
    model_name: str,
    count: int,
    out: IO[str],
    previous: list[str],
) -> int:
    written = 0
    for _ in range(count):
        content, max_tokens_used = await generate_no_thinking_with_retry(
            model_name=model_name,
            prompt=_build_prompt(spec, previous),
            temperature=TEMPERATURE,
            max_tokens=PLAYER_LINE_MAX_TOKENS,
        )
        message = content.strip('"')
        previous.append(message)
        print(f"  [{category}/{model_name}] {message!r}")
        out.write(
            json.dumps(
                {
                    "category": category,
                    "message": message,
                    "model": model_name,
                    "temperature": TEMPERATURE,
                    "max_tokens": max_tokens_used,
                }
            )
            + "\n"
        )
        out.flush()
        written += 1
    return written


def _categories_by_model() -> dict[str, list[str]]:
    """Group categories by their assigned model, preserving `SCENARIO_SPECS` order within
    each group, so every category sharing a model is generated in one uninterrupted batch
    before the next model is ever loaded."""
    grouped: dict[str, list[str]] = {}
    for category in SCENARIO_SPECS:
        grouped.setdefault(MODEL_ROTATION[category], []).append(category)
    return grouped


async def main() -> None:
    GENERATED_MESSAGES_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = _existing_messages_by_category()
    total = 0
    with GENERATED_MESSAGES_PATH.open("a") as out:
        for model_name, categories in _categories_by_model().items():
            pending = [
                category
                for category in categories
                if len(existing.get(category, [])) < REPEATS_PER_SCENARIO
            ]
            if not pending:
                print(f"Skipping '{model_name}': {categories} already have enough lines.")
                continue
            print(f"Loading '{model_name}' for categories {pending}...")
            switch_model(model_name)
            for category in pending:
                have = len(existing.get(category, []))
                remaining = REPEATS_PER_SCENARIO - have
                print(f"Generating {remaining} more line(s) for '{category}' ({have} saved)...")
                total += await _generate_and_save(
                    category,
                    SCENARIO_SPECS[category],
                    model_name=model_name,
                    count=remaining,
                    out=out,
                    previous=list(existing.get(category, [])),
                )

    print(f"\nWrote {total} generated messages to {GENERATED_MESSAGES_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
