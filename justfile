# ScientificState — cross-language build orchestration
# Requires: just, pnpm, uv

# ── Full system ───────────────────────────────────────────────────────────────

build-all: build-contracts build-ui build-framework build-domains build-daemon build-desktop

test-all: test-framework test-domains test-daemon test-ui test-desktop

lint-all: lint-framework lint-domains lint-daemon lint-js

validate-schemas:
    cd Core/contracts && pnpm run validate

# ── Core/framework ────────────────────────────────────────────────────────────

build-framework:
    cd Core/framework && uv build

test-framework:
    cd Core/framework && uv run pytest

lint-framework:
    cd Core/framework && uv run --extra dev ruff check .

# ── Domains ───────────────────────────────────────────────────────────────────

build-domains:
    cd Domains/polymer && uv build

test-domains:
    cd Domains/polymer && uv run pytest

lint-domains:
    cd Domains/polymer && uv run --extra dev ruff check .

# ── Core/daemon ───────────────────────────────────────────────────────────────

build-daemon:
    cd Core/daemon && uv build

test-daemon:
    cd Core/daemon && uv run pytest

lint-daemon:
    cd Core/daemon && uv run ruff check .

# ── JS / TS ───────────────────────────────────────────────────────────────────

build-ui:
    pnpm --filter @scientificstate/ui build

build-contracts:
    pnpm --filter @scientificstate/contracts build

build-desktop:
    pnpm --filter @scientificstate/desktop build

test-ui:
    pnpm --filter @scientificstate/ui test

test-desktop:
    pnpm --filter @scientificstate/desktop test

lint-js:
    pnpm turbo lint

# ── Tauri / Desktop ───────────────────────────────────────────────────────────

dev:
    cd Desktop && cargo tauri dev

# ── Phase 1 smoke — all subsystems must pass ──────────────────────────────────

phase1-smoke:
    @echo "=== contracts ==="
    cd Core/contracts && pnpm run validate && pnpm run build
    @echo "=== framework ==="
    cd Core/framework && uv run pytest -q
    @echo "=== polymer ==="
    cd Domains/polymer && uv run pytest -q
    @echo "=== daemon ==="
    cd Core/daemon && uv run pytest tests/ -q
    @echo "=== desktop ==="
    cd Desktop && npm run typecheck && npm run build
    @echo "✅ Phase 1 smoke PASS"
