# Contributing to ScientificState

Thank you for your interest in contributing. This document explains the process for all types of contributions.

---

## Contribution Process

1. **Fork** the repository.
2. **Create a branch** from `main` with a descriptive name (e.g., `feat/polymer-hca-improvement`, `fix/ssv-validation-edge-case`).
3. **Make changes** within your branch, following the code style guidelines below.
4. **Ensure CI is green** before requesting review (`just lint-all`, `just test-all`, `just validate-schemas` must all pass locally).
5. **Open a Pull Request** against `main` with a clear description of what changed and why.
6. **Review:** A maintainer will review your PR. Core area changes require `@scientificstate/core-team` approval (see below).
7. **Merge** happens after approval and CI green.

---

## Commit Message Format

Use short, imperative-mood messages:

```
add KMD series enrichment test for PEG polymer
fix SSV validation missing T-component edge case
refactor domain registry to use importlib.metadata
```

Avoid: `"Added some fixes"`, `"WIP"`, `"misc changes"`.

---

## Code Style

| Language   | Tool      | Command                                      |
|------------|-----------|----------------------------------------------|
| Python     | ruff      | `cd <package> && uv run ruff check .`        |
| TypeScript | eslint    | `pnpm turbo lint`                            |
| Rust       | clippy    | `cd Desktop/src-tauri && cargo clippy`       |

All lint commands are **read-only** (no `--fix`). Fix issues manually before submitting.

---

## Domain Module Contributions

Contributing a new domain module (e.g., `Domains/spectroscopy/`) requires:

1. **`module-manifest.schema.json` compliance** — your module's manifest must validate against
   `Core/contracts/jsonschema/module-manifest.schema.json`. Run `just validate-schemas` to confirm.
2. **`domain-module.schema.json` interface** — your `DomainModule` implementation must conform to
   `Core/contracts/jsonschema/domain-module.schema.json`. The `domain_id`, `domain_name`, `version`,
   `supported_data_types`, and `methods` fields are required.
3. **Entry point registration** — declare your entry point in `pyproject.toml`:
   ```toml
   [project.entry-points."scientificstate.domains"]
   your_domain_id = "your_package.domain_manifest:YourDomainClass"
   ```
4. **No framework bleed** — domain-specific logic must not appear in `Core/framework/`. The dependency
   direction is `Domains/ → Core/framework/`, never the reverse.
5. **Tests** — include a `tests/` directory with at minimum a smoke test that instantiates your
   `DomainModule` and calls `list_methods()`.

---

## Core Area Changes

Changes to these paths require approval from `@scientificstate/core-team`:

- `Core/framework/` — domain-agnostic scientific core (SSV, Claims, DomainRegistry, etc.)
- `Core/contracts/` — shared JSON Schema contracts and generated types

Rationale: these are authoritative contracts that all domain modules and the Desktop workbench depend on.
Breaking changes here affect the entire system.

When proposing a core change, include in your PR:
- Why the existing contract is insufficient.
- What downstream impact (domains, daemon, Desktop) you have assessed.
- Whether the change is additive-only or breaking.

---

## Reporting Issues

Open a GitHub Issue with:
- A minimal reproducible example.
- The output of `just lint-all` and `just test-all` if relevant.
- Your OS, Python version, and `uv --version`.

---

## Questions

For design questions before implementing, open a Discussion rather than a PR.
