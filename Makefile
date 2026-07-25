.PHONY: run test db-up db-down migrate

# Start Postgres (docker compose), apply migrations, then run the app with the
# postgres backend and the Telegram bot enabled — regardless of what .env has set,
# since these two are the point of "make run".
run: db-up
	@echo "Waiting for Postgres..."
	@for i in $$(seq 1 30); do \
		scripts/compose.sh exec -T postgres pg_isready -U "$${POSTGRES_USER:-rp_engine}" -d "$${POSTGRES_DB:-rp_engine}" >/dev/null 2>&1 && break; \
		sleep 1; \
	done
	uv run alembic upgrade head
	RP_ENGINE_PERSISTENCE_BACKEND=postgres RP_ENGINE_TELEGRAM_ENABLED=true \
		uv run python -m uvicorn --app-dir src rp_engine.app.main:app --host 0.0.0.0 --port 8000

# Full test suite (PG-gated tests skip without a live DB) + mypy (src/, the part
# CLAUDE.md holds to a fully-clean bar) + ruff.
test:
	uv run pytest
	uv run ruff check .
	uv run mypy src/

db-up:
	scripts/db_services.sh up

db-down:
	scripts/db_services.sh down

# One-time: copy data/ (JSON backend) into the running Postgres. See
# scripts/migrate_json_to_postgres.py for scope/idempotency notes. Add --dry-run
# to preview counts without writing.
migrate:
	uv run alembic upgrade head
	RP_ENGINE_PERSISTENCE_BACKEND=postgres uv run python scripts/migrate_json_to_postgres.py
