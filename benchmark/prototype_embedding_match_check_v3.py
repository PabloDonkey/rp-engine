"""PROTOTYPE — throwaway, not production code.

Third-model rerun of `prototype_embedding_match_check.py`. Same methodology, same 60
messages, same 4 lore entries — only the embedding model changes, so all three runs'
output is directly comparable.

Run 1 used nomic-embed-text-v1.5 (768-dim, ~137M params, 84 MB). Run 2 used bge-small-en-v1.5
(384-dim, 33M params, 37 MB) — a different, smaller architecture that fixed one problem but
introduced another. This run deliberately goes BIGGER instead of sideways: BAAI's
`bge-large-en-v1.5`, same BGE family/training approach as run 2's bge-small but roughly 10x
the parameter count (335M vs 33M) and about 3-4x nomic's params, to test whether scale within
a proven architecture actually helps separate genuine matches from false positives, rather
than just changing which false-match problem shows up.

Uses LM Studio's OpenAI-compatible `/v1/embeddings` endpoint with
`text-embedding-bge-large-en-v1.5` (BAAI's BGE-large, plain BERT architecture, contrastively
trained, same lineage as bge-small). 1024-dim, Q8_0 GGUF, 358.24 MB on disk, downloaded for
this test via `lms get` from CompendiumLabs/bge-large-en-v1.5-gguf on Hugging Face —
confirmed as `type: embeddings` and 335M params by `GET /api/v0/models` and `lms ls` on this
machine, not assumed.

Reads the same 60 baseline rows (one per unique message) from
`prototype_lore_relevance_check_results.jsonl`, embeds each message and each lore entry's
`content` field, computes cosine similarity, and reports per-message rankings plus
aggregate score distributions — no fixed similarity threshold is assumed going in.
"""

import json
import os
import statistics
import urllib.request
from pathlib import Path

from prototype_lore_relevance_fixture import LORE_ENTRIES, SCENARIO_SPECS

ROOT = Path(__file__).resolve().parent
RESULTS_PATH = ROOT / "prototype_lore_relevance_check_results.jsonl"

API_HOST = os.environ.get("RP_ENGINE_LMSTUDIO_API_HOST", "localhost:1234")
EMBEDDING_MODEL = "text-embedding-bge-large-en-v1.5"

# entry_id -> title, since matched_lore_ids in the results file uses titles.
TITLE_BY_ID = {entry["entry_id"]: entry["title"] for entry in LORE_ENTRIES}


def embed(texts: list[str]) -> list[list[float]]:
    """Batch-embed via LM Studio's OpenAI-compatible /v1/embeddings endpoint."""
    request = urllib.request.Request(
        f"http://{API_HOST}/v1/embeddings",
        data=json.dumps({"model": EMBEDDING_MODEL, "input": texts}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        body = json.loads(response.read())
    # LM Studio returns data items in the same order as input, each with an "index".
    ordered = sorted(body["data"], key=lambda item: item["index"])
    return [item["embedding"] for item in ordered]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    return dot / (norm_a * norm_b)


def load_baseline_rows() -> list[dict]:
    with open(RESULTS_PATH) as f:
        rows = [json.loads(line) for line in f]
    return [row for row in rows if row["variant"] == "baseline"]


def main() -> None:
    rows = load_baseline_rows()
    assert len(rows) == 60, f"expected 60 baseline rows, got {len(rows)}"

    lore_ids = [entry["entry_id"] for entry in LORE_ENTRIES]
    lore_texts = [entry["content"] for entry in LORE_ENTRIES]
    messages = [row["generated_message"] for row in rows]

    print(f"Embedding model: {EMBEDDING_MODEL} @ {API_HOST}")
    print(f"Embedding {len(lore_texts)} lore entries + {len(messages)} messages...\n")

    lore_vecs = embed(lore_texts)
    message_vecs = embed(messages)

    # Per-message similarity to each of the 4 lore entries.
    results = []
    for row, mvec in zip(rows, message_vecs):
        sims = {lore_ids[i]: cosine(mvec, lore_vecs[i]) for i in range(len(lore_ids))}
        ranked = sorted(sims.items(), key=lambda kv: kv[1], reverse=True)
        results.append(
            {
                "category": row["category"],
                "message": row["generated_message"],
                "matched_lore_ids_keyword": row["matched_lore_ids"],
                "sims": sims,
                "ranked": ranked,
            }
        )

    # --- print everything, grouped by category -----------------------------------------
    for category in SCENARIO_SPECS:
        print("=" * 100)
        print(f"CATEGORY: {category}")
        print("=" * 100)
        for r in results:
            if r["category"] != category:
                continue
            sim_str = ", ".join(f"{lid}={r['sims'][lid]:.3f}" for lid in lore_ids)
            top_id, top_score = r["ranked"][0]
            second_score = r["ranked"][1][1]
            gap = top_score - second_score
            kw = r["matched_lore_ids_keyword"] or "(none)"
            print(f"- \"{r['message']}\"")
            print(f"    keyword matched: {kw}")
            print(f"    {sim_str}")
            print(f"    top={top_id} ({top_score:.3f}), gap to 2nd={gap:.3f}")
        print()

    # --- aggregate score distributions --------------------------------------------------
    # "should match" = the top-ranked lore entry's score for near_miss / true_positive /
    # contradiction / dont_invent(forge) / collision messages that are genuinely on-topic
    # for SOME entry, i.e. every category except false_positive, using each message's own
    # top-scoring entry as the candidate "correct" match (this script does not hand-label
    # per-message ground truth beyond category; see the written report for per-message
    # judgment calls on the near_miss / true_positive / contradiction messages).
    should_match_categories = {"near_miss", "true_positive", "contradiction", "collision", "dont_invent"}
    should_match_scores = [
        r["ranked"][0][1] for r in results if r["category"] in should_match_categories
    ]
    false_positive_best_scores = [
        r["ranked"][0][1] for r in results if r["category"] == "false_positive"
    ]
    false_positive_restraint_scores = [
        r["sims"]["reya_restraint"] for r in results if r["category"] == "false_positive"
    ]

    def summarize(label: str, values: list[float]) -> None:
        print(
            f"{label}: n={len(values)} min={min(values):.3f} "
            f"median={statistics.median(values):.3f} max={max(values):.3f} "
            f"mean={statistics.mean(values):.3f}"
        )

    print("=" * 100)
    print("AGGREGATE DISTRIBUTIONS")
    print("=" * 100)
    summarize("Top-entry score, on-topic categories (near_miss/true_positive/contradiction/collision/dont_invent)", should_match_scores)
    summarize("Top-entry score, false_positive category (should NOT match anything)", false_positive_best_scores)
    summarize("reya_restraint score specifically, false_positive category", false_positive_restraint_scores)

    # near_miss / true_positive reya_restraint scores specifically, for direct comparison
    # against the false_positive reya_restraint scores above (both use the "strong"/
    # "strength" word).
    restraint_relevant = [
        r["sims"]["reya_restraint"] for r in results if r["category"] in {"near_miss", "true_positive"}
    ]
    summarize("reya_restraint score, near_miss+true_positive (genuinely about Reya's strength)", restraint_relevant)


if __name__ == "__main__":
    main()
