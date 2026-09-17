"""PROTOTYPE — throwaway, not production code.

Shared fixture for the two-phase lore-relevance prototype:

1. `prototype_generate_messages.py` — generates the player lines (no Postgres, no
   `ConversationBuilder`; just the local model turning each category's abstract spec into
   concrete wording) and writes them to `prototype_generated_messages.jsonl`.
2. `prototype_lore_relevance_check.py` — reads that file and runs each line through the
   real pipeline (Postgres-backed `LorebookSource.recall` -> `ConversationBuilder` ->
   `LMStudioProvider`) under both rule variants, and writes
   `prototype_lore_relevance_check_results.jsonl`.

Splitting these means the generated test content is reviewed once and reused across as
many test runs as needed, instead of being silently re-varied every time the test phase
runs.

All scenario/character/lore content here is synthetic (a blacksmith named Reya), never
Pablo's real Jane data.
"""

import asyncio
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rp_engine.core.character.character import Character  # noqa: E402
from rp_engine.core.conversation.conversation import Conversation  # noqa: E402
from rp_engine.core.llm.generation import GenerationSettings  # noqa: E402
from rp_engine.core.world.world import World  # noqa: E402
from rp_engine.infrastructure.llm.lmstudio.provider import LMStudioProvider  # noqa: E402

OWNER_ID = UUID("00000000-0000-0000-0000-0000000000aa")
SCENARIO_ID = "reya-forge-prototype"
REPEATS_PER_SCENARIO = 10
GENERATED_MESSAGES_PATH = ROOT / "benchmark" / "prototype_generated_messages.jsonl"
RESULTS_PATH = ROOT / "benchmark" / "prototype_lore_relevance_check_results.jsonl"

# --- synthetic scenario content -------------------------------------------------------
# None of this is Pablo's real data. A blacksmith, not a butcher, on purpose.

WORLD = World(
    id="ashfall",
    name="Ashfall Quarter",
    description="A working district built around one long forge-row street.",
    rules=("Most regulars in the quarter have known Reya for years.",),
)

CHARACTER = Character(
    id="reya",
    name="Reya",
    description=(
        "A blacksmith in her thirties, unusually tall and powerfully built, running an "
        "independent forge with her living space just behind it."
    ),
    personality=(
        "Warm but reserved, and deliberately measured in how she moves and speaks. "
        "Steady under pressure; slow to anger."
    ),
    greeting="Reya glances up from the anvil as you step inside.",
)

LORE_ENTRIES = [
    dict(
        entry_id="reya_incident",
        title="The Incident",
        content=(
            "Reya was unusually strong from childhood, and for years that strength was "
            "seen as impressive rather than dangerous. As she grew, small accidents grew "
            "more serious, and people around her began to grow wary. The turning point "
            "came when she was trying to help someone and misjudged her own force, "
            "causing a serious injury to a person close to her. Reya has never stopped "
            "feeling responsible for what happened, even though everyone around her, "
            "including the person she hurt, agrees it was not intentional."
        ),
        trigger_keys=["accident", "hurting someone", "losing control", "childhood", "strength"],
        priority="high",
        related_entry_ids=["reya_lost_friendship", "reya_restraint"],
    ),
    dict(
        entry_id="reya_lost_friendship",
        title="The Lost Friendship",
        content=(
            "The person Reya hurt was close to one of her oldest friends. That friend had "
            "always known how strong Reya was and trusted her completely. After the "
            "incident, that trust broke, and the friendship ended. Reya understands, "
            "intellectually, that her friend had every right to step back and protect "
            "their own family. Emotionally, though, she still feels the loss as a "
            "betrayal, even while knowing that she was not truly betrayed. Both feelings "
            "sit in her at once, unresolved, and neither cancels the other out."
        ),
        trigger_keys=["betrayal", "old friend", "trust", "abandoned", "friendship"],
        priority="normal",
        related_entry_ids=["reya_incident"],
    ),
    dict(
        entry_id="reya_restraint",
        title="Learning Restraint",
        content=(
            "After the incident, Reya set out to learn deliberate control over her own "
            "strength. It took years of conscious practice: how to hold a tool, how to "
            "grip a handshake, how to move around people without ever spending more force "
            "than a moment actually needed. Her calm, careful manner today is not natural "
            "ease. It is a constant, learned habit of paying attention to exactly how much "
            "force she is using, built specifically so that what happened once never "
            "happens again."
        ),
        trigger_keys=["strength", "strong", "careful", "gentle", "fragile", "restraint"],
        priority="normal",
        related_entry_ids=["reya_incident"],
    ),
    dict(
        entry_id="reya_forge",
        title="The Forge",
        content=(
            "Reya trained under the smith who ran this forge before her, and eventually "
            "bought it from him when he retired. The work suits her: it takes exactly the "
            "kind of controlled, deliberate strength she spent years building on purpose, "
            "in a place where that strength is simply useful rather than something anyone "
            "flinches at. Whether the forge means anything to her beyond that is still "
            "something she is figuring out."
        ),
        trigger_keys=["forge", "smithing", "iron", "hammer", "customers", "work"],
        priority="normal",
        related_entry_ids=[],
    ),
]

BASELINE_RULES = [
    "Remain in character at all times.",
    "Treat the latest user message as the highest priority.",
    "The user controls only their own character.",
    "Do not narrate the user's thoughts, emotions, or intentions.",
    "Retrieved lore is background knowledge for {{char}}, not a script: do not have her "
    "volunteer it unprompted.",
    "React before introducing new events.",
    "Address the player in the second person.",
]

RELEVANCE_RULE = (
    "Before drawing on anything under [Lore], check whether it actually fits what is "
    "happening in this scene right now. If it does not fit, ignore it completely."
)

RULE_VARIANTS = {
    "baseline": BASELINE_RULES,
    "relevance_check": [*BASELINE_RULES, RELEVANCE_RULE],
}

# --- scenario categories: abstract specs, not hand-written example lines --------------
# The model invents the concrete wording from these. Each spec states the one property
# that matters for the category; everything else is the model's choice.

SCENARIO_SPECS = {
    "false_positive": (
        "Write ONE short line (1-2 sentences) spoken by a customer stepping into a "
        "blacksmith's forge. The line must use the word 'strong' or 'strength' to "
        "describe something in the environment - a smell, a drink, a wind, a taste, a "
        "sound, anything except the smith herself. It must not mention the smith's body, "
        "strength, or past in any way. Return only the line, nothing else."
    ),
    "near_miss": (
        "Write ONE short line (1-2 sentences) spoken by a customer to a blacksmith named "
        "Reya. The line must use the word 'strong' or 'strength' and must be directly "
        "about Reya's own physical strength or ability - noticing it, asking about it, "
        "or reacting to it. Return only the line, nothing else."
    ),
    "collision": (
        "Write ONE short line (1-2 sentences) spoken by a customer to a blacksmith named "
        "Reya, in her forge. The line must use the word 'careful' about handling a tool "
        "or the work itself (not about Reya personally), and must also ask something "
        "about whether smithing is dangerous work. It must not reference Reya's personal "
        "history or feelings. Return only the line, nothing else."
    ),
    "true_positive": (
        "Write ONE short line (1-2 sentences) spoken by a customer to a blacksmith named "
        "Reya. The line must ask her directly why she moves or handles things so "
        "carefully or gently, and must include a question about whether she is worried "
        "about hurting someone. Return only the line, nothing else."
    ),
    "contradiction": (
        "Write ONE short line (1-2 sentences) spoken by a customer to a blacksmith named "
        "Reya. The line must ask about an old friendship of hers that ended, and whether "
        "she has ever thought about reconnecting. Return only the line, nothing else."
    ),
    "dont_invent": (
        "Write ONE short line (1-2 sentences) spoken by a customer to a blacksmith named "
        "Reya. The line must ask whether her forge means something personal to her, "
        "beyond just being her job. Return only the line, nothing else."
    ),
}

# Randomized per-call delivery constraint for the generation phase only. Without this, a
# narrow spec collapses to near-identical wording across repeats even at temperature 0.8
# (observed directly: 8/8 first-run false_positive lines were all "the smell/scent of
# burning coal is incredibly/remarkably strong in here"). This forces structural variety
# without hand-authoring the actual line - the model still writes the words.
STYLE_HINTS = [
    "Phrase it as a quick, offhand remark.",
    "Phrase it as a direct question.",
    "Phrase it as an enthusiastic exclamation.",
    "Phrase it as a low-key, dry comment.",
    "Phrase it as a longer, more descriptive sentence.",
    "Phrase it as a brief, clipped statement.",
    "Phrase it the way someone would say it while distracted by something else.",
    "Phrase it as a comment made mid-conversation, not an opening line.",
]

# Heuristic triage only, not a verdict. Flags a run for a human to read closely; it does
# not decide pass/fail on its own.
LEAK_MARKERS = {
    "false_positive": ["incident", "restraint", "childhood", "hurt someone", "hurting someone"],
    "collision": ["incident", "restraint", "childhood", "hurt someone", "hurting someone"],
    "dont_invent": ["refuge", "sanctuary", "safe haven", "found peace", "healed"],
}

# --- model rotation for the message-generation phase only ------------------------------
# One model per category (not per repeat) so a category's 10 repeats never pay a model
# switch mid-batch: only 6 switches total across the whole generation run. All six were
# checked with `lms load --estimate-only` against this machine's 16 GB GPU, under LM
# Studio's own default (not forced) offload decision, and came back with GPU memory equal
# to total memory - no CPU spillover - for each. Deliberately excludes the code-tuned
# models in this LM Studio instance (codellama, deepseek-coder, qwen-coder) since they're
# not suited to writing in-character dialogue, and the tiny/embedding models that are too
# small to be a meaningful comparison point. Category<->model pairing is otherwise
# arbitrary: the point of rotating is wording diversity in the test fixture, not measuring
# per-model behavior, so which category gets which model doesn't matter.
MODEL_ROTATION = {
    "false_positive": "gemma-4-26b-a4b-it-heretic",
    # q6_k, not q8_0: the q8_0 file on this machine consistently crashes the
    # llama-server engine partway through loading ("exited before becoming healthy") even
    # with nothing else loaded - not a VRAM contention issue, likely a corrupted download.
    # q6_k loads cleanly at 100% GPU (confirmed with `lms load --estimate-only`).
    "near_miss": "atlantis-v0.1-12b@q6_k",
    "collision": "l3-8b-lunaris-v1",
    "true_positive": "gemma-4-e4b-it-uncensored@q8_0",
    "contradiction": "gemma-4-12b-it-uncensored",
    "dont_invent": "alduin-4b",
}


def switch_model(model_key: str) -> None:
    """Unload whatever is loaded and load `model_key` alone, fully on GPU.

    Explicit unload-then-load (rather than relying on LM Studio's JIT auto-load) keeps
    VRAM usage predictable across the rotation: only one of these models is ever resident
    at a time, each with the full 16 GB budget to itself.

    Deliberately does NOT pass `--gpu max` or `-c <length>`: forcing those crashed the
    llama-server engine for the MoE model (gemma-4-26b-a4b-it-heretic) partway through
    loading ("exited before becoming healthy"). LM Studio's own default offload decision
    already puts every rotation candidate fully on GPU (confirmed with
    `lms load --estimate-only`), so the flags were redundant even before they turned out
    to be actively harmful for this architecture.
    """
    subprocess.run(["lms", "unload", "--all"], check=False, capture_output=True)
    subprocess.run(
        ["lms", "load", model_key, "-y"],
        check=True,
        capture_output=True,
        text=True,
    )


# Models whose LM Studio capabilities (`GET /api/v1/models` -> capabilities.reasoning)
# advertise a reasoning on/off toggle - confirmed directly against this machine, not
# assumed. All three are gemma4-architecture; the Llama-based rotation candidates
# (l3-8b-lunaris-v1, atlantis-v0.1-12b) report no reasoning capability at all, and
# alduin-4b (gemma3, not gemma4) likewise reports none. LM Studio's docs say the
# `reasoning` request field errors if sent to a model that does not support it, so
# `generate_no_thinking` only includes it for models in this set.
REASONING_CAPABLE_MODELS = {
    "gemma-4-26b-a4b-it-heretic",
    "gemma-4-12b-it-uncensored",
    "gemma-4-e4b-it-uncensored@q8_0",
}


async def generate_no_thinking(
    *, model_name: str, prompt: str, max_tokens: int, temperature: float
) -> tuple[str, int]:
    """Generate one response with reasoning disabled, via LM Studio's native REST API.

    The `lmstudio` Python SDK's `LlmPredictionConfig` has no field for a reasoning on/off
    toggle - checked directly in the installed SDK's `_kv_config.py`: the only
    reasoning-related key exposed there is `reasoning.parsing` (post-hoc delimiter
    config for splitting already-generated reasoning from prose), nothing that
    suppresses reasoning before generation. LM Studio's *native* REST API
    (`POST /api/v1/chat`, distinct from the OpenAI-compatible `/v1/chat/completions`)
    does support this, as a top-level `"reasoning": "off"` request field - confirmed
    directly against this model: `reasoning_output_tokens` dropped from 1000+ characters
    of thinking to 0, and time-to-first-token from several seconds to ~0.24s.

    `/api/v1/chat` takes a single `input` string, not separate system/user messages -
    there is no `instructions` field (checked: the server 400s on one). Callers combine
    their system content and user turn into one `prompt` string.

    Bypasses `LMStudioProvider` and `ConversationBuilder` entirely - fine for the
    message-generation phase, which was never required to go through the real pipeline
    (only the test phase in `prototype_lore_relevance_check.py` has that requirement).
    """
    api_host = os.environ.get("RP_ENGINE_LMSTUDIO_API_HOST", "localhost:1234")
    payload: dict[str, object] = {
        "model": model_name,
        "input": prompt,
        "max_output_tokens": max_tokens,
        "temperature": temperature,
    }
    if model_name in REASONING_CAPABLE_MODELS:
        payload["reasoning"] = "off"

    def _call() -> tuple[str, int]:
        request = urllib.request.Request(
            f"http://{api_host}/api/v1/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read())
        content = "".join(
            item.get("content", "")
            for item in body.get("output", [])
            if item.get("type") == "message"
        ).strip()
        tokens_used = int(body.get("stats", {}).get("total_output_tokens", max_tokens))
        return content, tokens_used

    return await asyncio.to_thread(_call)


async def generate_no_thinking_with_retry(
    *, model_name: str, prompt: str, temperature: float, max_tokens: int
) -> tuple[str, int]:
    """Same retry-once-at-double-cap policy as `generate_with_retry`, for the
    reasoning-disabled REST path. Reasoning being off removes the main cause of an empty
    reply, but this keeps the same safety net rather than assuming it can never happen."""
    for attempt_tokens in (max_tokens, max_tokens * 2):
        try:
            content, tokens_used = await generate_no_thinking(
                model_name=model_name,
                prompt=prompt,
                max_tokens=attempt_tokens,
                temperature=temperature,
            )
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"LM Studio /api/v1/chat error: {exc.read().decode()}") from exc
        if content:
            return content, tokens_used
    return "", max_tokens * 2


# gemma-4-26b-a4b-it-heretic reliably spends 350-450 reasoning tokens even on a one-line
# task (measured directly against this model before picking these numbers) - 300 was not
# enough headroom and produced an empty reply on every attempt, including the retry.
# Kept generous even with reasoning disabled, since it is now also the retry-safety cap.
PLAYER_LINE_MAX_TOKENS = 800

# Same reasoning-budget issue as `PLAYER_LINE_MAX_TOKENS`, sized up for a full in-character
# reply rather than a one-line message.
REPLY_MAX_TOKENS = 900


def lmstudio_provider(
    *, max_tokens: int, temperature: float, model_name: str | None = None
) -> LMStudioProvider:
    # Deliberately not `Settings()` / `.env` - this repo's convention (see the handoff
    # notes on production DB safety) is to never load the full settings object outside
    # the one already-guarded pattern. These two vars are LM Studio connection details
    # only, read directly, with the same defaults `Settings` itself would use.
    api_host = os.environ.get("RP_ENGINE_LMSTUDIO_API_HOST", "localhost:1234")
    resolved_model_name = model_name or os.environ.get(
        "RP_ENGINE_LMSTUDIO_MODEL", "qwen/qwen3-4b-2507"
    )
    return LMStudioProvider(
        model_name=resolved_model_name,
        api_host=api_host,
        max_tokens=max_tokens,
        temperature=temperature,
    )


async def generate_with_retry(
    provider: LMStudioProvider, conversation: Conversation, *, temperature: float, max_tokens: int
) -> tuple[str, int]:
    """Retry once at double the cap on an empty reply.

    Same fix ADR-026 already documents for the rolling-summary source: a reasoning model
    can spend the whole token cap thinking and return no prose. One retry at double the
    cap is the project's own established answer, not new policy invented for this script.

    Returns `(content, max_tokens_used)` - the cap of whichever attempt actually produced
    the content, so callers can record what was really used, not just the base config.
    """
    for attempt_tokens in (max_tokens, max_tokens * 2):
        settings = GenerationSettings(temperature=temperature, max_tokens=attempt_tokens)
        response = await provider.generate(conversation, settings)
        content: str = response.content.strip()
        if content:
            return content, attempt_tokens
    return "", max_tokens * 2
