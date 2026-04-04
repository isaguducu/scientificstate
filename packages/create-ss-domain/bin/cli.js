#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

const SNAKE_CASE_RE = /^[a-z][a-z0-9_]*$/;

function validateDomainId(id) {
  if (!id || typeof id !== "string") {
    return "domain_id is required";
  }
  if (!SNAKE_CASE_RE.test(id)) {
    return `domain_id '${id}' is invalid — must be snake_case (e.g. polymer_science, biology)`;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Template generators
// ---------------------------------------------------------------------------

function domainManifest(domainId) {
  const displayName = domainId
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");

  return JSON.stringify(
    {
      domain_id: domainId,
      display_name: displayName,
      version: "0.1.0",
      description: `${displayName} domain plugin for ScientificState`,
      methods: [
        {
          method_id: "example_analysis",
          display_name: "Example Analysis",
          description: "A placeholder method — replace with your domain logic",
        },
      ],
      dependencies: [],
    },
    null,
    2,
  );
}

function pyprojectToml(domainId) {
  return `[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "scientificstate-domain-${domainId.replace(/_/g, "-")}"
version = "0.1.0"
description = "ScientificState domain plugin: ${domainId}"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio"]
`;
}

function srcInit(domainId) {
  const className = domainId
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join("");

  return `"""${domainId} domain plugin for ScientificState."""
from __future__ import annotations


class ${className}Domain:
    """Domain plugin entry point."""

    domain_id = "${domainId}"

    def execute_method(self, method_id: str, params: dict) -> dict:
        """Dispatch to the appropriate method handler."""
        from .methods import example_method

        handlers = {
            "example_analysis": example_method.run,
        }
        handler = handlers.get(method_id)
        if handler is None:
            return {
                "method_id": method_id,
                "domain_id": self.domain_id,
                "status": "error",
                "error_code": "METHOD_NOT_FOUND",
                "error": f"Unknown method: {method_id}",
                "diagnostics": {},
            }
        return handler(params)
`;
}

function methodsInit() {
  return `"""Domain methods package."""
`;
}

function exampleMethod(domainId) {
  return `"""Example analysis method — replace with real domain logic."""
from __future__ import annotations


def run(params: dict) -> dict:
    """Execute the example analysis.

    Parameters
    ----------
    params : dict
        Input parameters for the analysis.

    Returns
    -------
    dict
        Domain method output (fed to result_adapter).
    """
    return {
        "method_id": "example_analysis",
        "domain_id": "${domainId}",
        "status": "ok",
        "result": {
            "summary": "Example analysis completed",
            "input_params": params,
        },
        "diagnostics": {
            "runtime_ms": 0,
        },
    }
`;
}

function resultAdapter(domainId) {
  return `"""result_adapter.py — ${domainId} domain SSV result adapter.

Converts domain execute_method() output to the SSV 7-tuple format.

SSV 7-tuple fields (all lowercase):
  d — data hash / fingerprint
  i — instrument / method identifier
  a — analyst / actor identifier
  t — timestamp (ISO 8601)
  r — result summary
  u — uncertainty / confidence
  v — version of the analysis
  p — provenance chain reference
"""
from __future__ import annotations

from datetime import datetime, timezone


def adapt_to_ssv(method_output: dict, run_context: dict) -> dict:
    """Convert method output to SSV 7-tuple.

    Parameters
    ----------
    method_output : dict
        Returned by the domain's execute_method().
    run_context : dict
        Daemon-supplied context (run_id, workspace_id, etc.).

    Returns
    -------
    dict
        SSV record with lowercase 7-tuple fields: d, i, a, t, r, u, v, p.
    """
    now = datetime.now(tz=timezone.utc).isoformat()

    return {
        "d": run_context.get("data_hash", ""),
        "i": method_output.get("method_id", ""),
        "a": run_context.get("actor_id", ""),
        "t": now,
        "r": str(method_output.get("result", {}).get("summary", "")),
        "u": str(method_output.get("diagnostics", {}).get("confidence", "N/A")),
        "v": "0.1.0",
        "p": run_context.get("run_id", ""),
    }
`;
}

function testsInit() {
  return `"""Test package."""
`;
}

function conftest(domainId) {
  const className = domainId
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join("");

  return `"""Shared fixtures for ${domainId} tests."""
import pytest
from src import ${className}Domain


@pytest.fixture
def domain():
    return ${className}Domain()
`;
}

function testExampleMethod(domainId) {
  return `"""Tests for example_method."""
from src.methods.example_method import run


def test_example_returns_ok():
    result = run({"input": "test"})
    assert result["status"] == "ok"
    assert result["domain_id"] == "${domainId}"
    assert result["method_id"] == "example_analysis"


def test_example_includes_diagnostics():
    result = run({})
    assert "diagnostics" in result
    assert "runtime_ms" in result["diagnostics"]
`;
}

function readmeContent(domainId) {
  const displayName = domainId
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");

  return `# ${displayName} Domain Plugin

A ScientificState domain plugin for ${displayName}.

## Quick Start

\`\`\`bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -q
\`\`\`

## Structure

- \`scientificstate-domain.json\` — Domain manifest
- \`src/\` — Domain implementation
  - \`methods/\` — Analysis method handlers
  - \`result_adapter.py\` — SSV 7-tuple adapter
- \`tests/\` — Test suite
`;
}

// ---------------------------------------------------------------------------
// Scaffold function
// ---------------------------------------------------------------------------

function scaffold(domainId, baseDir) {
  const domainDir = path.join(baseDir, `Domains/${domainId}`);

  if (fs.existsSync(domainDir)) {
    return { error: `Directory already exists: ${domainDir}` };
  }

  const files = {
    "scientificstate-domain.json": domainManifest(domainId),
    "pyproject.toml": pyprojectToml(domainId),
    "README.md": readmeContent(domainId),
    "src/__init__.py": srcInit(domainId),
    "src/methods/__init__.py": methodsInit(),
    "src/methods/example_method.py": exampleMethod(domainId),
    "src/result_adapter.py": resultAdapter(domainId),
    "tests/__init__.py": testsInit(),
    "tests/conftest.py": conftest(domainId),
    "tests/test_example_method.py": testExampleMethod(domainId),
  };

  // Create all files
  for (const [relPath, content] of Object.entries(files)) {
    const fullPath = path.join(domainDir, relPath);
    fs.mkdirSync(path.dirname(fullPath), { recursive: true });
    fs.writeFileSync(fullPath, content, "utf-8");
  }

  return { domainDir, files: Object.keys(files) };
}

// ---------------------------------------------------------------------------
// CLI entry point
// ---------------------------------------------------------------------------

function main() {
  const args = process.argv.slice(2);

  if (args.includes("--help") || args.includes("-h") || args.length === 0) {
    console.log(`
create-ss-domain — Scaffold a new ScientificState domain plugin

Usage:
  create-ss-domain <domain_id>

Arguments:
  domain_id   Snake_case domain identifier (e.g. polymer_science, biology)

Options:
  --help, -h  Show this help message

Examples:
  create-ss-domain materials_science
  create-ss-domain quantum_chemistry
    `.trim());
    process.exit(args.includes("--help") || args.includes("-h") ? 0 : 1);
  }

  const domainId = args[0];

  const validationError = validateDomainId(domainId);
  if (validationError) {
    console.error(`Error: ${validationError}`);
    process.exit(1);
  }

  // Find project root (look for justfile or .git)
  let baseDir = process.cwd();
  let current = baseDir;
  while (current !== path.dirname(current)) {
    if (
      fs.existsSync(path.join(current, "justfile")) ||
      fs.existsSync(path.join(current, ".git"))
    ) {
      baseDir = current;
      break;
    }
    current = path.dirname(current);
  }

  const result = scaffold(domainId, baseDir);

  if (result.error) {
    console.error(`Error: ${result.error}`);
    process.exit(1);
  }

  console.log(`
Domain plugin scaffolded successfully!

  Directory: ${result.domainDir}
  Files created: ${result.files.length}

Next steps:
  1. cd ${result.domainDir}
  2. Edit scientificstate-domain.json to add your methods
  3. Implement method handlers in src/methods/
  4. Update src/result_adapter.py for your SSV mapping
  5. Write tests (target: 50+ tests)
  6. pip install -e ".[dev]" && pytest tests/ -q
  `.trim());
}

// Export for testing
module.exports = { validateDomainId, scaffold, domainManifest, resultAdapter };

// Run if invoked directly
if (require.main === module) {
  main();
}
