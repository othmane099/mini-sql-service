set dotenv-load := true

# List available recipes
default:
    @just --list

# Install all dependencies
install:
    uv sync --all-groups

# Start the development server
dev:
    uv run uvicorn main:app --app-dir src --reload --host 0.0.0.0 --port 8000

# Run linter
lint:
    uv run ruff check src/ --fix

# Run formatter
format:
    uv run ruff format src/

# Check formatting without writing changes
format-check:
    uv run ruff format --check src/

# Lint + format check (CI gate)
check:
    just lint
    just format-check

# Apply all pending migrations
migrate:
    uv run alembic upgrade head

# Roll back the last migration
migrate-down:
    uv run alembic downgrade -1

# Generate a new migration (usage: just migration "add some table")
migration name:
    uv run alembic revision --autogenerate -m "{{ name }}"

# Show current migration state
migrate-status:
    uv run alembic current

# Show migration history
migrate-history:
    uv run alembic history --verbose
