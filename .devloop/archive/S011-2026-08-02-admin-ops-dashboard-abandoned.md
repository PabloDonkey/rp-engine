> 🗄️ **ARCHIVED — ABANDONED 2026-08-02.** Frozen; do not edit. Never built.
> **Why:** Not needed. This was scoped as the third admin-panel slice back when the panel was
> new; a single-operator engine on a tailnet has no ops problem a dashboard would solve — the
> questions it was going to answer (is the DB up, is the schema current, what did the model do)
> are already answered by `/health`, the boot-time probe warning (S007), and the per-message
> debug menu (S012). Picking it up later means a **new epic**, not reopening this one.

# S011 · Admin panel — ops dashboard

**Status:** ⛔ ABANDONED (2026-08-02) — was 🔵 Backlog (follow-up to
[S009](S009-2026-07-27-admin-panel-session-debugging.md))
**Effort:** ~1 day (never spent)
**Risk:** Low (read-only aggregation)

## Context

Third slice of the admin panel (see S009 for product/interview decisions). The landing view:
a high-level **ops/health overview** rather than editing — active session counts, DB status,
recent errors, LLM latency. Reuses the S007 `/health` probe (`db` availability + schema-version
drift) and generation-trace data.

## Tasks (not done)
- [ ] `GET /admin/overview` — aggregates: total users, active/total sessions, messages over a
      window, DB health (reuse `PostgresHealthProbe`), recent generation-trace latency/errors.
- [ ] Frontend dashboard page as the panel's home route: stat tiles + a couple of small charts
      (follow the `dataviz` skill for any chart work).
- [ ] Surface DB schema-drift warning from the health probe prominently.

## Verification (not run)
- [ ] Backend suite green; overview numbers match a hand-count against the DB on a seeded dataset.
- [ ] Live-verify the dashboard renders real counts over the tailnet.
