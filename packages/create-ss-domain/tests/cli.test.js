const { describe, it, before, after } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { execSync } = require("node:child_process");
const { validateDomainId, scaffold, resultAdapter } = require("../bin/cli.js");

const TMP_DIR = path.join(__dirname, "__tmp_test__");

describe("create-ss-domain CLI", () => {
  before(() => {
    fs.mkdirSync(path.join(TMP_DIR, "Domains"), { recursive: true });
  });

  after(() => {
    fs.rmSync(TMP_DIR, { recursive: true, force: true });
  });

  // -----------------------------------------------------------------------
  // Test 1: Scaffolds domain with valid snake_case id
  // -----------------------------------------------------------------------
  it("scaffolds a domain with valid snake_case id", () => {
    const result = scaffold("test_domain", TMP_DIR);
    assert.ok(!result.error, `Unexpected error: ${result.error}`);
    assert.ok(result.domainDir.endsWith("Domains/test_domain"));
    assert.ok(result.files.length >= 8);

    // Check key files exist
    const manifest = path.join(result.domainDir, "scientificstate-domain.json");
    assert.ok(fs.existsSync(manifest), "Manifest should exist");

    const parsed = JSON.parse(fs.readFileSync(manifest, "utf-8"));
    assert.equal(parsed.domain_id, "test_domain");
    assert.equal(parsed.version, "0.1.0");
    assert.ok(parsed.methods.length >= 1);
  });

  // -----------------------------------------------------------------------
  // Test 2: Rejects non-snake_case id
  // -----------------------------------------------------------------------
  it("rejects non-snake_case domain id", () => {
    assert.ok(validateDomainId("CamelCase") !== null);
    assert.ok(validateDomainId("has-hyphen") !== null);
    assert.ok(validateDomainId("123start") !== null);
    assert.ok(validateDomainId("has space") !== null);
    assert.ok(validateDomainId("") !== null);
    assert.ok(validateDomainId(null) !== null);

    // Valid ones
    assert.equal(validateDomainId("polymer_science"), null);
    assert.equal(validateDomainId("biology"), null);
    assert.equal(validateDomainId("quantum_chemistry"), null);
  });

  // -----------------------------------------------------------------------
  // Test 3: Rejects existing directory
  // -----------------------------------------------------------------------
  it("rejects when directory already exists", () => {
    // test_domain was created in test 1
    const result = scaffold("test_domain", TMP_DIR);
    assert.ok(result.error);
    assert.ok(result.error.includes("already exists"));
  });

  // -----------------------------------------------------------------------
  // Test 4: Generates correct SSV field names (lowercase d,i,a,t,r,u,v,p)
  // -----------------------------------------------------------------------
  it("generates result_adapter with lowercase SSV 7-tuple fields", () => {
    const adapterPath = path.join(
      TMP_DIR,
      "Domains/test_domain/src/result_adapter.py",
    );
    assert.ok(fs.existsSync(adapterPath), "result_adapter.py should exist");

    const content = fs.readFileSync(adapterPath, "utf-8");
    // Check all 7-tuple fields appear as dict keys
    const requiredFields = ['"d"', '"i"', '"a"', '"t"', '"r"', '"u"', '"v"', '"p"'];
    for (const field of requiredFields) {
      assert.ok(
        content.includes(field),
        `result_adapter.py must contain SSV field ${field}`,
      );
    }
    // Ensure no uppercase SSV fields
    const uppercaseFields = ['"D":', '"I":', '"A":', '"T":', '"R":', '"U":', '"V":', '"P":'];
    for (const field of uppercaseFields) {
      assert.ok(
        !content.includes(field),
        `result_adapter.py must NOT contain uppercase field ${field}`,
      );
    }
  });

  // -----------------------------------------------------------------------
  // Test 5: Shows help with --help
  // -----------------------------------------------------------------------
  it("shows help with --help flag", () => {
    const cliPath = path.join(__dirname, "..", "bin", "cli.js");
    const output = execSync(`"${process.execPath}" "${cliPath}" --help`, {
      encoding: "utf-8",
    });
    assert.ok(output.includes("create-ss-domain"));
    assert.ok(output.includes("Usage"));
    assert.ok(output.includes("domain_id"));
    assert.ok(output.toLowerCase().includes("snake_case"));
  });
});
