# TODO(S024): write `assert_lorebook_store_contract`, exercised against
# `PostgresLorebookStore` via whatever the reworked engine-testing setup turns out to be
# (see the parallel session rebuilding the Postgres/testcontainers test approach — hold
# off wiring this into that harness until it lands).
#
# Follow `session_summary_store_contract.py`'s shape: create a scenario, then assert
# save/get/list_for_scenario/delete are scoped correctly by (scenario_definition_id, id)
# and that `save` upserts in place rather than duplicating a row.
#
# The one case worth real Postgres for: `find_matching` should return an entry for
# recall text that only shares a *stem* with one of its trigger keys (e.g. "dragons"
# matching a trigger of "dragon" — the ADR-026 example, confirmed by hand against a real
# database: `to_tsvector('english', 'dragons')` and `to_tsvector('english', 'dragon')`
# both produce the lexeme `dragon`). Do not reuse "strength"/"strong" as a stemming
# example — checked the same way, Postgres's english stemmer treats them as unrelated
# lexemes (`strength` stays `strength`, `strong` stays `strong`), so a trigger of
# "strong" will not fire on text that only says "strength". Also assert that text
# sharing no stem with any entry's triggers matches nothing. That is the whole reason
# this layer uses `to_tsvector`/`to_tsquery` instead of a substring check (ADR-026,
# `docs/MEMORY.md` layer 02).
