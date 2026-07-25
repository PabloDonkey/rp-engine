# S011 · Admin panel — ops dashboard

**Status:** 🔵 Backlog (follow-up to [S009](S009-admin-panel-session-debugging.md))
**Effort:** ~1 day
**Risk:** Low (read-only aggregation)

## Context

Third slice of the admin panel (see S009 for product/interview decisions). The landing view:
a high-level **ops/health overview** rather than editing — active session counts, DB status,
recent errors, LLM latency. Reuses the S007 `/health` probe (`db` availability + schema-version
drift) and generation-trace data.

## Tasks
- [ ] `GET /admin/overview` — aggregates: total users, active/total sessions, messages over a
      window, DB health (reuse `PostgresHealthProbe`), recent generation-trace latency/errors.
- [ ] Frontend dashboard page as the panel's home route: stat tiles + a couple of small charts
      (follow the `dataviz` skill for any chart work).
- [ ] Surface DB schema-drift warning from the health probe prominently.

## Verification
- [ ] Backend suite green; overview numbers match a hand-count against the DB on a seeded dataset.
- [ ] Live-verify the dashboard renders real counts over the tailnet.
