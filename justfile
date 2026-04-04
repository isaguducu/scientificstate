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

# ── Phase 2 smoke — Phase 1 + lint gates + web build ─────────────────────────

phase2-smoke:
    @echo "=== contracts ==="
    cd Core/contracts && pnpm run validate && pnpm run build
    @echo "=== framework tests ==="
    cd Core/framework && uv run pytest -q
    @echo "=== framework lint ==="
    cd Core/framework && uv run ruff check .
    @echo "=== polymer tests ==="
    cd Domains/polymer && uv run pytest -q
    @echo "=== polymer lint ==="
    cd Domains/polymer && uv run ruff check .
    @echo "=== daemon tests ==="
    cd Core/daemon && uv run pytest tests/ -q
    @echo "=== daemon lint ==="
    cd Core/daemon && uv run ruff check .
    @echo "=== web build ==="
    cd Web && npm run build
    @echo "=== desktop ==="
    cd Desktop && npm run typecheck && npm run build
    @echo "✅ Phase 2 smoke PASS"

# ── Phase 3 smoke — Phase 2 + sandbox + standards + tuf + federation + i18n + diagnostics ─

phase3-smoke:
    @echo "=== contracts ==="
    cd Core/contracts && pnpm run validate && pnpm run build
    @echo "=== framework tests (sandbox + standards + tuf delegated dahil) ==="
    cd Core/framework && uv run pytest -q
    @echo "=== framework lint ==="
    cd Core/framework && uv run ruff check .
    @echo "=== polymer tests ==="
    cd Domains/polymer && uv run pytest -q
    @echo "=== polymer lint ==="
    cd Domains/polymer && uv run ruff check .
    @echo "=== daemon tests (export + registry + diagnostics routes dahil) ==="
    cd Core/daemon && uv run pytest tests/ -q
    @echo "=== daemon lint ==="
    cd Core/daemon && uv run ruff check .
    @echo "=== web build (federation + SSO pages dahil) ==="
    cd Web && npm run build
    @echo "=== desktop (i18n dahil) ==="
    cd Desktop && npm run typecheck && npm run build
    @echo "✅ Phase 3 smoke PASS"

# ── Phase 4 smoke — Phase 3 + table alignment + monitoring + security audit ───

phase4-smoke:
    @echo "=== contracts ==="
    cd Core/contracts && pnpm run validate && pnpm run build
    @echo "=== framework tests ==="
    cd Core/framework && uv run pytest -q
    @echo "=== framework lint ==="
    cd Core/framework && uv run ruff check .
    @echo "=== polymer tests ==="
    cd Domains/polymer && uv run pytest -q
    @echo "=== polymer lint ==="
    cd Domains/polymer && uv run ruff check .
    @echo "=== daemon tests (table alignment + monitoring dahil) ==="
    cd Core/daemon && uv run pytest tests/ -q
    @echo "=== daemon lint ==="
    cd Core/daemon && uv run ruff check .
    @echo "=== web build ==="
    cd Web && npm run build
    @echo "=== desktop ==="
    cd Desktop && npm run typecheck && npm run build
    @echo "✅ Phase 4 smoke PASS"

# ── Phase 5 smoke — Phase 4 + alerting + materials + shared-ui ────────────────

phase5-smoke:
    @echo "=== contracts ==="
    cd Core/contracts && pnpm run validate && pnpm run build
    @echo "=== framework tests ==="
    cd Core/framework && uv run pytest -q
    @echo "=== framework lint ==="
    cd Core/framework && uv run ruff check .
    @echo "=== polymer tests ==="
    cd Domains/polymer && uv run pytest -q
    @echo "=== materials tests ==="
    cd Domains/materials && uv run pytest -q
    @echo "=== daemon tests (alerting + monitoring dahil) ==="
    cd Core/daemon && uv run pytest tests/ -q
    @echo "=== daemon lint ==="
    cd Core/daemon && uv run ruff check .
    @echo "=== web build ==="
    cd Web && npm run build
    @echo "=== desktop (analytics dahil) ==="
    cd Desktop && npm run typecheck && npm run build
    @echo "=== shared ui ==="
    cd Core/ui && npm run build
    @echo "✅ Phase 5 smoke PASS"

# ── Phase 6 smoke — Phase 5 + all domains + cross-domain + mobile + i18n + recommendation ──

phase6-smoke:
    @echo "=== contracts ==="
    cd Core/contracts && pnpm run validate && pnpm run build
    @echo "=== framework tests ==="
    cd Core/framework && uv run pytest -q
    @echo "=== framework lint ==="
    cd Core/framework && uv run ruff check .
    @echo "=== polymer tests ==="
    cd Domains/polymer && uv run pytest -q
    @echo "=== materials tests ==="
    cd Domains/materials && uv run pytest -q
    @echo "=== biology tests ==="
    cd Domains/biology && uv run pytest -q
    @echo "=== chemistry tests ==="
    cd Domains/chemistry && uv run pytest -q
    @echo "=== daemon tests ==="
    cd Core/daemon && uv run pytest tests/ -q
    @echo "=== daemon lint ==="
    cd Core/daemon && uv run ruff check .
    @echo "=== web build ==="
    cd Web && npm run build
    @echo "=== desktop ==="
    cd Desktop && npm run typecheck && npm run build
    @echo "=== shared ui ==="
    cd Core/ui && npm run build
    @echo "=== mobile ==="
    cd Mobile && npx expo export --platform web
    @echo "=== i18n check ==="
    node scripts/check-i18n-keys.js
    @echo "✅ Phase 6 smoke PASS"

# ── Phase 7 smoke — full integration hardening ───────────────────────────

phase7-smoke:
    @echo "=== contracts ==="
    cd Core/contracts && pnpm run validate && pnpm run build
    @echo "=== framework tests ==="
    cd Core/framework && uv run pytest -q
    @echo "=== framework lint ==="
    cd Core/framework && uv run ruff check .
    @echo "=== polymer tests ==="
    cd Domains/polymer && uv run pytest -q
    @echo "=== materials tests ==="
    cd Domains/materials && uv run pytest -q
    @echo "=== biology tests ==="
    cd Domains/biology && uv run pytest -q
    @echo "=== chemistry tests ==="
    cd Domains/chemistry && uv run pytest -q
    @echo "=== daemon tests ==="
    cd Core/daemon && uv run pytest tests/ -q
    @echo "=== daemon lint ==="
    cd Core/daemon && uv run ruff check .
    @echo "=== quantum backend ==="
    cd Core/daemon && uv run pytest tests/test_quantum_backend.py tests/test_quantum_sim_backend.py -q
    @echo "=== federation tests ==="
    cd Core/daemon && uv run pytest tests/test_federation_sync.py -q
    @echo "=== audit tests ==="
    cd Core/daemon && uv run pytest tests/test_audit.py -q
    @echo "=== platform smoke ==="
    cd Core/daemon && uv run pytest tests/test_platform_smoke.py -q
    @echo "=== integration hardening ==="
    cd Core/daemon && uv run pytest tests/test_integration_hardening.py -q
    @echo "=== web build ==="
    cd Web && npm run build
    @echo "=== desktop ==="
    cd Desktop && npm run typecheck && npm run build
    @echo "=== shared ui ==="
    cd Core/ui && npm run build
    @echo "=== mobile ==="
    cd Mobile && npx expo export --platform web
    @echo "=== i18n check ==="
    node scripts/check-i18n-keys.js
    @echo "=== plugin sdk ==="
    cd packages/create-ss-domain && npm test
    @echo "✅ Phase 7 smoke PASS"
