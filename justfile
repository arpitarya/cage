# Cage — task runner. Same $0/stdlib constitution as fux (plan §1).
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

# Smoke: seed a demo task, then prove the attribution thesis end-to-end.
demo:
    {{python}} -m cage demo
    {{python}} -m cage insights attrib
    {{python}} -m cage insights matrix

# Install the engine (editable) so repo edits live-reflect in the `cage` binary.
install:
    ./install.sh

# Build cage.pyz locally (a smoke build — the release asset is CI-built only).
pyz:
    {{python}} -m tools.buildpyz --out dist-pyz/cage.pyz
