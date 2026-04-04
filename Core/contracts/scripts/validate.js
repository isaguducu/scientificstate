#!/usr/bin/env node
/**
 * ScientificState Contract Validation Script
 * Validates all JSON Schema fixtures using AJV.
 * Part of W2 Contracts — Day 2 acceptance criteria.
 *
 * Usage: node scripts/validate.js
 * Exit code: 0 = all pass, 1 = any failure
 */

import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");

function loadJSON(relPath) {
  const abs = resolve(ROOT, relPath);
  return JSON.parse(readFileSync(abs, "utf-8"));
}

function run() {
  const ajv = new Ajv2020({
    strict: false,
    allErrors: true,
  });
  addFormats(ajv);

  // Load all schemas (must add all before compiling to resolve cross-refs)
  const schemas = {
    "claim-lifecycle": loadJSON("jsonschema/claim-lifecycle.schema.json"),
    "report-projection": loadJSON("jsonschema/report-projection.schema.json"),
    "ssv": loadJSON("jsonschema/ssv.schema.json"),
    "claim": loadJSON("jsonschema/claim.schema.json"),
    "domain-module": loadJSON("jsonschema/domain-module.schema.json"),
    "module-manifest": loadJSON("jsonschema/module-manifest.schema.json"),
    "compute-run-request": loadJSON("jsonschema/compute-run-request.schema.json"),
    "compute-run-result": loadJSON("jsonschema/compute-run-result.schema.json"),
    "module-permission": loadJSON("jsonschema/module-permission.schema.json"),
    "module-store-entry": loadJSON("jsonschema/module-store-entry.schema.json"),
    "module-publish-request": loadJSON("jsonschema/module-publish-request.schema.json"),
    "quantum-run-request": loadJSON("jsonschema/quantum-run-request.schema.json"),
    "quantum-run-result": loadJSON("jsonschema/quantum-run-result.schema.json"),
    "replication-request": loadJSON("jsonschema/replication-request.schema.json"),
    "replication-result": loadJSON("jsonschema/replication-result.schema.json"),
    "rocrate-profile": loadJSON("jsonschema/rocrate-profile.schema.json"),
    "citation": loadJSON("jsonschema/citation.schema.json"),
    "claim-collection": loadJSON("jsonschema/claim-collection.schema.json"),
  };

  // Add all schemas to AJV registry first (enables cross-$ref resolution)
  for (const [, schema] of Object.entries(schemas)) {
    ajv.addSchema(schema);
  }

  const fixtures = [
    {
      label: "claim-lifecycle",
      schema: schemas["claim-lifecycle"],
      fixture: loadJSON("tests/fixtures/sample-lifecycle.json"),
    },
    {
      label: "report-projection",
      schema: schemas["report-projection"],
      fixture: loadJSON("tests/fixtures/sample-report.json"),
    },
    {
      label: "ssv",
      schema: schemas["ssv"],
      fixture: loadJSON("tests/fixtures/sample-ssv.json"),
    },
    {
      label: "claim",
      schema: schemas["claim"],
      fixture: loadJSON("tests/fixtures/sample-claim.json"),
    },
    {
      label: "domain-module",
      schema: schemas["domain-module"],
      fixture: loadJSON("tests/fixtures/sample-domain.json"),
    },
    {
      label: "module-manifest",
      schema: schemas["module-manifest"],
      fixture: loadJSON("tests/fixtures/sample-module-manifest.json"),
    },
    {
      label: "compute-run-request",
      schema: schemas["compute-run-request"],
      fixture: loadJSON("tests/fixtures/compute_run_request.json"),
    },
    {
      label: "compute-run-result (success)",
      schema: schemas["compute-run-result"],
      fixture: loadJSON("tests/fixtures/compute_run_result_success.json"),
    },
    {
      label: "compute-run-result (error)",
      schema: schemas["compute-run-result"],
      fixture: loadJSON("tests/fixtures/compute_run_result_error.json"),
    },
    {
      label: "module-store-entry",
      schema: schemas["module-store-entry"],
      fixture: loadJSON("tests/fixtures/sample-module-store-entry.json"),
    },
    {
      label: "module-publish-request",
      schema: schemas["module-publish-request"],
      fixture: loadJSON("tests/fixtures/sample-module-publish-request.json"),
    },
    {
      label: "quantum-run-request",
      schema: schemas["quantum-run-request"],
      fixture: loadJSON("tests/fixtures/sample-quantum-run-request.json"),
    },
    {
      label: "quantum-run-result",
      schema: schemas["quantum-run-result"],
      fixture: loadJSON("tests/fixtures/sample-quantum-run-result.json"),
    },
    {
      label: "replication-request",
      schema: schemas["replication-request"],
      fixture: loadJSON("tests/fixtures/sample-replication-request.json"),
    },
    {
      label: "replication-result",
      schema: schemas["replication-result"],
      fixture: loadJSON("tests/fixtures/sample-replication-result.json"),
    },
    {
      label: "citation",
      schema: schemas["citation"],
      fixture: loadJSON("tests/fixtures/sample-citation.json"),
    },
    {
      label: "claim-collection",
      schema: schemas["claim-collection"],
      fixture: loadJSON("tests/fixtures/sample-claim-collection.json"),
    },
  ];

  let allPassed = true;

  for (const { label, schema, fixture } of fixtures) {
    const validate = ajv.compile(schema);
    const valid = validate(fixture);
    if (valid) {
      console.log(`  ✓ ${label}`);
    } else {
      console.error(`  ✗ ${label}`);
      for (const err of validate.errors ?? []) {
        console.error(`      ${err.instancePath || "/"} — ${err.message}`);
      }
      allPassed = false;
    }
  }

  if (allPassed) {
    console.log("\nAll contract schemas validated successfully.");
    process.exit(0);
  } else {
    console.error("\nContract validation FAILED — see errors above.");
    process.exit(1);
  }
}

run();
