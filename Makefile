.PHONY: run stop test db-up db-down

APP_PORT := 8000

# Start Postgres (docker compose), apply migrations, then run the app with the
# Telegram bot enabled — regardless of what .env has set, since these two are the
# point of "make run". Frees the app port first (see `stop`) so re-running after a
# previous instance was left running doesn't fail with "address already in use".
run: db-up stop
	@echo "Waiting for Postgres..."
	@for i in $$(seq 1 30); do \
		scripts/compose.sh exec -T postgres pg_isready -U "$${POSTGRES_USER:-rp_engine}" -d "$${POSTGRES_DB:-rp_engine}" >/dev/null 2>&1 && break; \
		sleep 1; \
	done
	uv run alembic upgrade head
	RP_ENGINE_TELEGRAM_ENABLED=true \
		uv run python -m uvicorn --app-dir src rp_engine.app.main:app --host 0.0.0.0 --port $(APP_PORT)

# Kill whatever is listening on the app port (a previous `make run` left running, an
# orphaned uvicorn, etc). Safe to run when nothing is listening — fuser just no-ops.
stop:
	@fuser -k $(APP_PORT)/tcp 2>/dev/null; sleep 1; true

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
