.PHONY: run test db-up db-down

# Start Postgres (docker compose), apply migrations, then run the app with the
# Telegram bot enabled — regardless of what .env has set, since these two are the
# point of "make run".
run: db-up
	@echo "Waiting for Postgres..."
	@for i in $$(seq 1 30); do \
		scripts/compose.sh exec -T postgres pg_isready -U "$${POSTGRES_USER:-rp_engine}" -d "$${POSTGRES_DB:-rp_engine}" >/dev/null 2>&1 && break; \
		sleep 1; \
	done
	uv run alembic upgrade head
	RP_ENGINE_TELEGRAM_ENABLED=true \
		uv run python -m uvicorn --app-dir src rp_engine.app.main:app --host 0.0.0.0 --port 8000

# Full test suite (spins up a throwaway Postgres via testcontainers, see tests/conftest.py)
# + mypy (src/, the part CLAUDE.md holds to a fully-clean bar) + ruff.
test:
	uv run pytest
	uv run ruff check .
	uv run mypy src/

db-up:
	scripts/db_services.sh up

db-down:
	scripts/db_services.sh down
