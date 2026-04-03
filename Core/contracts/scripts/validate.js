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
