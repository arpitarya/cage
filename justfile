# Cage — task runner. Same $0/stdlib constitution as fux (README.md).
python := env_var_or_default("CAGE_PYTHON", "python3.14")

# List recipes
default:
    @just --list

# Run the test suite
test:
    {{python}} -m pytest -q

# Lint (ruff if available; no-op otherwise)
lint:
    @command -v ruff >/dev/null 2>&1 && ruff check cage || echo "ruff not installed — skipping"

# Build cage.pyz locally (a smoke build — the release asset is CI-built only).
pyz:
    {{python}} -m tools.buildpyz --out dist-pyz/cage.pyz
