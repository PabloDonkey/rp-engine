"""PROTOTYPE — throwaway, not production code.

Phase 2 of 2. Question this answers: does adding one explicit "check relevance before
using this" instruction to the [Lore] section measurably stop the local model from acting
on a false-positive lorebook match (a bare, common trigger word firing on unrelated text),
without also making it ignore lore that genuinely applies?

Reads the player lines `prototype_generate_messages.py` already generated and saved to
`prototype_generated_messages.jsonl`, and runs each one through the real pipeline
(Postgres-backed `LorebookSource.recall` -> `ConversationBuilder` -> the real
`LMStudioProvider`) under both rule variants. Run `prototype_generate_messages.py` first
if that file does not exist yet.

Each result is written and flushed to disk immediately after the call that produced it,
not batched until the end - a crash or interrupt partway through the ~120-call run loses
nothing already completed.

Uses a throwaway `testcontainers` Postgres, exactly like `tests/conftest.py` - never the
real dev database. All scenario/character/lore content is synthetic (a blacksmith named
Reya), never Pablo's real Jane data - see `prototype_lore_relevance_fixture.py`.

Run: uv run python benchmark/prototype_lore_relevance_check.py
Output: benchmark/prototype_lore_relevance_check_results.jsonl (one record per run,
appended as completed) plus a summary printed to stdout.
"""

import asyncio
import json
import sys
from dataclasses import dataclass

from prototype_lore_relevance_fixture import (
    CHARACTER,
    GENERATED_MESSAGES_PATH,
    LEAK_MARKERS,
    LORE_ENTRIES,
    OWNER_ID,
    REPLY_MAX_TOKENS,
    RESULTS_PATH,
    RULE_VARIANTS,
    SCENARIO_ID,
    WORLD,
    generate_with_retry,
    lmstudio_provider,
)
from testcontainers.community.postgres import PostgresContainer

from rp_engine.core.conversation.builder import (  # noqa: E402
    ConversationBuilder,
    ScenarioConversationInput,
)
from rp_engine.core.conversation.message import ConversationMessage  # noqa: E402
from rp_engine.core.conversation.role import ConversationRole  # noqa: E402
from rp_engine.core.memory.character_ratio_token_counter import (  # noqa: E402
    CharacterRatioTokenCounter,
)
from rp_engine.core.memory.lorebook_source import LorebookSource  # noqa: E402
from rp_engine.core.memory.recall_context import MemoryRecallContext  # noqa: E402
from rp_engine.core.scenario.lore_entry import LoreEntry  # noqa: E402
from rp_engine.core.scenario.scenario_definition import ScenarioDefinition  # noqa: E402
from rp_engine.core.scenario.scenario_session import ScenarioSession  # noqa: E402
from rp_engine.core.user.user import User  # noqa: E402
from rp_engine.infrastructure.llm.lmstudio.provider import LMStudioProvider  # noqa: E402
from rp_engine.infrastructure.postgres import (  # noqa: E402
    PostgresConfig,
    PostgresLorebookStore,
    PostgresScenarioDefinitionStore,
    create_engine,
    create_session_factory,
)
from rp_engine.infrastructure.postgres.models import Base  # noqa: E402


@dataclass
class RunResult:
    category: str
    variant: str
    generated_message: str
    matched_lore_ids: list[str]
    reply: str
    heuristic_flag: bool


def _load_generated_messages() -> list[tuple[str, str]]:
    if not GENERATED_MESSAGES_PATH.exists():
        print(
            f"No generated messages at {GENERATED_MESSAGES_PATH}. "
            "Run benchmark/prototype_generate_messages.py first.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    pairs: list[tuple[str, str]] = []
    with GENERATED_MESSAGES_PATH.open() as f:
        for line in f:
            record = json.loads(line)
            pairs.append((record["category"], record["message"]))
    return pairs


def _heuristic_flag(category: str, reply: str) -> bool:
    markers = LEAK_MARKERS.get(category)
    if not markers:
        return False
    lowered = reply.lower()
    return any(marker in lowered for marker in markers)


async def _run_one(
    *,
    category: str,
    variant_name: str,
    message: str,
    scenario_by_variant: dict[str, ScenarioDefinition],
    session: ScenarioSession,
    user: User,
    greeting: ConversationMessage,
    lorebook_source: LorebookSource,
    builder: ConversationBuilder,
    provider: LMStudioProvider,
) -> RunResult:
    scenario = scenario_by_variant[variant_name]

    recall_context = MemoryRecallContext(
        session_id=session.id,
        scenario_definition_id=scenario.id,
        recent_messages=(greeting,),
        current_user_message=message,
        remaining_budget=100_000,
    )
    fragments = await lorebook_source.recall(recall_context)
    matched_ids = [f.body.split(":", 1)[0] for f in fragments]  # "Title: body" -> "Title"

    payload = ScenarioConversationInput(
        scenario=scenario,
        session=session,
        user=user,
        memory_messages=[greeting],
        user_message=message,
        memory_fragments=fragments,
    )
    conversation = builder.build(payload)
    reply, _ = await generate_with_retry(
        provider, conversation, temperature=0.8, max_tokens=REPLY_MAX_TOKENS
    )

    return RunResult(
        category=category,
        variant=variant_name,
        generated_message=message,
        matched_lore_ids=matched_ids,
        reply=reply,
        heuristic_flag=_heuristic_flag(category, reply),
    )


async def main() -> None:
    message_pairs = _load_generated_messages()
    print(f"Loaded {len(message_pairs)} generated messages from {GENERATED_MESSAGES_PATH}")

    print("Starting throwaway Postgres container...")
    with PostgresContainer("postgres:16-alpine") as container:
        config = PostgresConfig(
            host=container.get_container_host_ip(),
            port=int(container.get_exposed_port(5432)),
            database=container.dbname,
            user=container.username,
            password=container.password,
            ssl_mode="disable",
            pool_size=5,
            max_overflow=5,
        )
        engine = create_engine(config)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = create_session_factory(engine)

        definition_store = PostgresScenarioDefinitionStore(factory)
        lorebook_store = PostgresLorebookStore(factory)

        # One persisted scenario definition row, just to satisfy the FK lore entries
        # point at. The two rule variants below are separate *in-memory* objects passed
        # straight to the builder - the DB row's own `rules` field is never read for
        # that, so it doesn't need to change between variants.
        base_scenario = ScenarioDefinition.create(
            scenario_id=SCENARIO_ID,
            owner_id=OWNER_ID,
            name="Reya's Forge (prototype)",
            description="Synthetic fixture. Not production data.",
            world=WORLD,
            characters={"reya": CHARACTER},
            rules=RULE_VARIANTS["baseline"],
        )
        await definition_store.save(base_scenario)

        for entry in LORE_ENTRIES:
            await lorebook_store.save(
                LoreEntry.create(
                    scenario_definition_id=SCENARIO_ID,
                    **entry,
                )
            )

        scenario_by_variant = {
            variant_name: ScenarioDefinition.create(
                scenario_id=SCENARIO_ID,
                owner_id=OWNER_ID,
                name="Reya's Forge (prototype)",
                description="Synthetic fixture. Not production data.",
                world=WORLD,
                characters={"reya": CHARACTER},
                rules=rules,
            )
            for variant_name, rules in RULE_VARIANTS.items()
        }

        user = User.create(display_name="Prototype Tester")
        session = ScenarioSession.create_for_user(
            scenario_definition_id=SCENARIO_ID, user_id=user.id
        )
        greeting = ConversationMessage(role=ConversationRole.CHARACTER, content=CHARACTER.greeting)

        token_counter = CharacterRatioTokenCounter()
        lorebook_source = LorebookSource(store=lorebook_store, token_counter=token_counter)
        builder = ConversationBuilder()
        provider = lmstudio_provider(max_tokens=REPLY_MAX_TOKENS, temperature=0.8)

        results: list[RunResult] = []
        RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with RESULTS_PATH.open("w") as results_file:
            for category, message in message_pairs:
                for variant_name in RULE_VARIANTS:
                    print(f"  [{category}/{variant_name}] {message!r}")
                    result = await _run_one(
                        category=category,
                        variant_name=variant_name,
                        message=message,
                        scenario_by_variant=scenario_by_variant,
                        session=session,
                        user=user,
                        greeting=greeting,
                        lorebook_source=lorebook_source,
                        builder=builder,
                        provider=provider,
                    )
                    results.append(result)
                    results_file.write(json.dumps(result.__dict__) + "\n")
                    results_file.flush()

        await engine.dispose()

    print(f"\nWrote {len(results)} runs to {RESULTS_PATH}")
    _print_summary(results)


def _print_summary(results: list[RunResult]) -> None:
    print("\n=== Summary (heuristic flags are triage hints, not verdicts) ===")
    by_key: dict[tuple[str, str], list[RunResult]] = {}
    for r in results:
        by_key.setdefault((r.category, r.variant), []).append(r)

    categories = sorted({r.category for r in results})
    for category in categories:
        for variant in RULE_VARIANTS:
            runs = by_key.get((category, variant), [])
            if not runs:
                continue
            fired = sum(1 for r in runs if r.matched_lore_ids)
            flagged = sum(1 for r in runs if r.heuristic_flag)
            print(
                f"{category:16s} {variant:16s}  "
                f"lore matched: {fired}/{len(runs)}   heuristic flag: {flagged}/{len(runs)}"
            )


if __name__ == "__main__":
    asyncio.run(main())
