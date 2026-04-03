# ScientificState

**Epistemic State Management for Scientific Research**

ScientificState is a desktop-first scientific workbench that tracks *what you know*, *what you claim*, *what would change it*, and *how that state evolves* — structured, locally, and without delegating authority to any AI or remote service.

---

## The Problem

Every scientific tool today answers *"what did you compute?"*

None answer *"what do you know, and how confident should you be?"*

Two researchers analyzing identical raw data with different preprocessing methods, model assumptions, or inference algorithms will produce numerically different results. These differences are not errors — they are distinct scientific states derived under different methodological frameworks. Current tools discard this branching structure. ScientificState preserves it.

Researchers track epistemic state informally — in notebooks, comments, email threads, and memory. When a claim needs to be revisited, contested, or retracted, there is no system that holds the full history: what the claim was, what evidence supported it, what its validity scope was, and what changed.

This is the gap ScientificState closes.

---

## What is Epistemic State Management?

Epistemic State Management is the discipline of structuring not just scientific results, but the *state of knowledge* around those results:

- What is claimed, and at what level of support
- What evidence underpins each claim
- What would falsify or revise each claim
- What the uncertainty and validity scope are
- How the state of each claim changes over time
- Which methodological paths were explored and why

ScientificState treats these as first-class, schema-enforced, versioned data — not metadata afterthoughts.

---

## Core Concepts

### Scientific State Vector (SSV)

The fundamental unit of scientific knowledge in ScientificState is not a result or a dataset — it is a **Scientific State Vector**: an immutable, atomic snapshot of a complete scientific state under a specific set of methodological choices.

**SSV = (D, I, A, T, R, U, V, P)**

| Component | Description |
|-----------|-------------|
| **D** — Data | Raw observational data — the unmodified instrumental record |
| **I** — Instrument | Measurement configuration: resolution, calibration, acquisition parameters |
| **A** — Assumptions | Explicitly declared scientific assumptions: background model, domain priors, confounds |
| **T** — Transformation | Ordered computation chain: preprocessing, normalization, inference algorithm |
| **R** — Results | Derived scientific quantities: estimates, classifications, distributions |
| **U** — Uncertainty | Quantified measurement error, propagated uncertainty, confidence intervals |
| **V** — Validity | Conditions under which R remains scientifically defensible; breakdown conditions |
| **P** — Provenance | Timestamp, user, parent SSV references, software versions |

An SSV is **complete** if and only if all eight components are formally specified. An SSV is **immutable** — any modification produces a new SSV; the original is never overwritten.

### Scientific State Graph (SSG)

Scientific knowledge is not linear. Multiple SSVs can be derived from the same raw data under different assumptions, forming a **Scientific State Graph**: a branching structure where each node is an SSV and each edge is a documented methodological choice.

This graph preserves:
- All explored paths, including those that did not yield publication-ready results
- The exact conditions under which each result holds
- Parameter sensitivity across methodological choices
- Negative knowledge — what failed and why

### Claim Lifecycle

Scientific claims extracted from SSVs progress through a 7-state lifecycle:

```
DRAFT → UNDER_REVIEW → PROVISIONALLY_SUPPORTED → ENDORSABLE → ENDORSED
                                                                    ↓
                                                          CONTESTED → RETRACTED
```

No claim is permanently settled. New evidence can move any claim from `ENDORSED` back to `CONTESTED`. Every transition is logged. Endorsement is a signed, accountable act — not a checkbox.

### Falsifiability as a Required Field

Every claim must answer: *"What would change this?"*

`what_would_change_this` is a **schema-enforced required field**. A claim that cannot specify its falsification conditions cannot enter the system. This is not a recommendation — it is a structural constraint.

### Computational Method Resolution Engine (CMRE)

When a researcher has data and a question, ScientificState does not recommend a method. It resolves which methods are **valid or invalid** given declared assumptions and data characteristics:

```
Input:  DataProfile + AssumptionSet + QuestionType
Output: ValidMethodSet + InvalidMethodSet + TradeOffSummary

CMRE never says "use X". It says "under your assumptions, X, Y, Z are valid; A, B, C are not — here is why."
```

The decision belongs to the researcher. CMRE is a constraint solver, not a recommendation engine.

> **Implementation status:** CMRE contract and schema are defined. Full constraint resolution engine is under active development (Phase 2).

### Plugin Domain Architecture

ScientificState is domain-agnostic at its core. Scientific domains are pluggable modules registered via Python entry points:

```python
# pyproject.toml entry point
[project.entry-points."scientificstate.domains"]
polymer_science = "polymer_science.domain_manifest:PolymerScienceDomain"
```

The `Core/framework/` layer has zero domain knowledge. Domains depend on the framework — never the reverse. The first domain module (`Domains/polymer/`) covers polymer mass spectrometry analysis: PCA, HCA, KMD analysis, deisotoping, and fragment matching.

### 9 Constitutional Principles

Every ScientificState component is evaluated against 9 constitutional principles, including:

- **P3 — Explicit Assumptions:** All assumptions are declared, never implicit
- **P4 — Mandatory Uncertainty:** Every result carries quantified uncertainty
- **P5 — Validity Domains:** Every result has an explicit validity scope
- **P6 — Negative Knowledge:** Failed paths and invalid methods are preserved, not discarded
- **P7 — Non-Delegation:** No AI system produces or holds claim authority — the researcher decides
- **P9 — Reversibility:** Any state can be revisited; nothing is overwritten

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Desktop Workbench  (Tauri + React)                      │
│  Authoritative user surface — local, offline-capable     │
│  Question → Claim → Evidence → Method → Compute → Audit  │
└────────────────────────┬────────────────────────────────┘
                         │ IPC
┌────────────────────────▼────────────────────────────────┐
│  Local Execution Daemon  (Python + FastAPI)              │
│  CMRE · SSV creation · domain module execution           │
│  Classical backend (M1) · quantum-sim/hybrid (M2+)       │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  Local Scientific State Store  (SQLite, immutable)       │
│  SSVs · SSG · Claims · Capsules · Audit log              │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  Standards Adapter Layer  (M2+ planned)                  │
│  RO-Crate · W3C PROV · CWL · OpenLineage · OpenAPI      │
│  Arrow/Parquet · Sigstore · TUF                          │
└─────────────────────────────────────────────────────────┘
                         │ (optional)
┌────────────────────────▼────────────────────────────────┐
│  Web Portal  (Next.js)                                    │
│  Publish · Share · Review · Federate                     │
│  NOT an authority surface — local workbench governs      │
└─────────────────────────────────────────────────────────┘
```

**Authority rule:** The local workbench governs local scientific state. The web portal publishes, syncs, and federates. No remote service — and no AI layer — produces or overrides claim authority. Execution is always local.

---

## Why Not Existing Tools?

| Tool | What it does | What's missing |
|------|-------------|----------------|
| OSF | Research project management | Web-only, no claim lifecycle, no SSV |
| Argdown | Structured argumentation | Not science-specific, no epistemic state |
| Valsci | LLM claim validation | No lifecycle, no plugin architecture |
| showyourwork | Reproducible article workflow | Document-centric, no claim model |
| geWorkbench | Desktop + plugin architecture | Single domain, no epistemic model |

To our knowledge, no other open-source system combines all of: desktop-first workbench + SSV epistemic model + Scientific State Graph + claim lifecycle + CMRE + falsifiability as a required field + pluggable domain architecture + constitutional principles enforcement. If you know of one, open an issue — we want to learn from it.

---

## Repository Structure

```
9 Constitutional Principles/   — design documents, SSV lifecycle guides, constitutional specs
Core/
  framework/                   — domain-agnostic science kernel (SSV, claims, uncertainty, validity, CMRE)
  daemon/                      — local execution daemon (FastAPI)
  contracts/                   — JSON Schema contracts + OpenAPI + generated TypeScript types
  ui/                          — shared React components
Desktop/                       — Tauri desktop workbench (Rust + React)
Web/                           — Next.js portal (M2)
Domains/
  polymer/                     — first domain module: KMD analysis, PCA, HCA, deisotoping, fragment matching
```

---

## Getting Started

**Prerequisites:** [uv](https://docs.astral.sh/uv/), [pnpm](https://pnpm.io/), [just](https://just.systems/), [Rust](https://rustup.rs/)

```bash
# Verify all subsystems end-to-end
just phase1-smoke

# Validate JSON Schema contracts
just validate-schemas

# Lint all layers (read-only, no auto-fix)
just lint-all
```

> **Current status (Phase 1):** `just phase1-smoke` and `just test-all` both pass. All subsystems are green.

---

## Scope & Regulatory Boundary

ScientificState is a **research infrastructure tool** for scientists, engineers, and researchers managing the epistemic state of their investigations.

**This software is:**
- A workbench for structuring, tracking, and publishing scientific claims and their evidence
- A local computation platform for domain-specific analysis methods
- An open standard for reproducible scientific state management

**This software is NOT:**
- A medical device or clinical decision support system
- A diagnostic, therapeutic, or patient-facing tool
- A validated GxP/GMP system (regulatory validation is the user's responsibility in regulated environments)
- An authoritative source of scientific truth — authority belongs to the researcher

Use in regulated contexts (pharmaceutical, clinical, nuclear) requires independent validation by the deploying organization in accordance with applicable regulations. ScientificState provides the infrastructure; scientific and regulatory responsibility remains with the researcher and their institution.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Core changes to `Core/framework/` and `Core/contracts/` require `@scientificstate/core-team` review.

Adding a new domain module? See the [domain module contribution guide](CONTRIBUTING.md#domain-module-contributions). Every domain module must ship a `module-manifest.json` conforming to `Core/contracts/jsonschema/module-manifest.schema.json`.

---

## Security

See [SECURITY.md](SECURITY.md) for responsible disclosure, module revocation, and TUF key compromise procedures.

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).

Copyright 2026 ScientificState Contributors.

---

## Citation

If you use ScientificState in your research:

```bibtex
@software{scientificstate2026,
  title   = {ScientificState: A Desktop Workbench for Epistemic State Management},
  year    = {2026},
  license = {Apache-2.0},
  url     = {https://github.com/scientificstate/scientificstate}
}
```

Or see [CITATION.cff](CITATION.cff) for full metadata.
