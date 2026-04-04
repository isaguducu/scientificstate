#!/usr/bin/env node
/**
 * i18n key sync checker — verifies all locales have the same keys as en.json.
 *
 * Checks 7 locales × 3 platforms (Desktop, Web, Mobile) = 21 files.
 * en.json is the reference — missing keys in other locales are reported as errors.
 * Exit code 1 if any keys are missing.
 */

const fs = require("fs");
const path = require("path");

const LOCALES = ["en", "tr", "de", "fr", "es", "zh", "ja"];
const I18N_DIRS = ["Desktop/src/i18n", "Web/i18n", "Mobile/src/i18n"];

/**
 * Flatten a nested JSON object into dot-separated key paths.
 * e.g. { nav: { home: "Home" } } → ["nav.home"]
 */
function flattenKeys(obj, prefix = "") {
  const keys = [];
  for (const [k, v] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${k}` : k;
    if (typeof v === "object" && v !== null && !Array.isArray(v)) {
      keys.push(...flattenKeys(v, fullKey));
    } else {
      keys.push(fullKey);
    }
  }
  return keys;
}

let totalErrors = 0;
let totalFiles = 0;

for (const dir of I18N_DIRS) {
  const absDir = path.resolve(__dirname, "..", dir);

  // Check if directory exists
  if (!fs.existsSync(absDir)) {
    console.error(`SKIP: ${dir} does not exist`);
    continue;
  }

  // Load reference (en.json)
  const enPath = path.join(absDir, "en.json");
  if (!fs.existsSync(enPath)) {
    console.error(`ERROR: ${dir}/en.json not found (reference file)`);
    totalErrors++;
    continue;
  }

  const enData = JSON.parse(fs.readFileSync(enPath, "utf-8"));
  const enKeys = flattenKeys(enData);

  console.log(`\n=== ${dir} (${enKeys.length} keys in en.json) ===`);

  for (const locale of LOCALES) {
    if (locale === "en") continue;

    const localePath = path.join(absDir, `${locale}.json`);
    totalFiles++;

    if (!fs.existsSync(localePath)) {
      console.error(`  MISSING: ${locale}.json does not exist`);
      totalErrors++;
      continue;
    }

    const localeData = JSON.parse(fs.readFileSync(localePath, "utf-8"));
    const localeKeys = new Set(flattenKeys(localeData));

    const missing = enKeys.filter((k) => !localeKeys.has(k));

    if (missing.length > 0) {
      console.error(`  ${locale}.json: ${missing.length} missing key(s)`);
      for (const m of missing) {
        console.error(`    - ${m}`);
      }
      totalErrors++;
    } else {
      console.log(`  ${locale}.json: OK`);
    }
  }
}

console.log(`\n--- Summary ---`);
console.log(`Platforms: ${I18N_DIRS.length}`);
console.log(`Locale files checked: ${totalFiles}`);
console.log(`Errors: ${totalErrors}`);

if (totalErrors > 0) {
  console.error("\nFAILED: i18n keys out of sync");
  process.exit(1);
} else {
  console.log("\nPASSED: all i18n keys in sync");
}
