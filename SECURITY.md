# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| main    | Yes       |

Only the `main` branch receives security fixes. Older tags are not patched.

---

## Reporting a Vulnerability

We take security seriously. **Please do not open a public GitHub issue for security vulnerabilities.**

### Responsible Disclosure Process

1. **Identify** the vulnerability and prepare a clear description including:
   - Affected component (e.g., `Core/daemon`, `Domains/polymer`, Desktop Tauri shell)
   - Steps to reproduce
   - Potential impact assessment
   - Suggested fix (optional but appreciated)

2. **Report privately** using one of the following channels:
   - **Email:** security@scientificstate.org
   - **GitHub Security Advisories:** [Report a vulnerability](https://github.com/scientificstate/scientificstate/security/advisories/new)

3. **Response timeline:**
   - **48 hours:** Initial acknowledgment of your report.
   - **7 days:** Preliminary severity assessment and triage decision.
   - **90 days:** Target for patch release (coordinated disclosure window).

4. **Coordinated disclosure:** We ask that you do not publicly disclose the vulnerability
   until we have released a fix or the 90-day window has elapsed, whichever comes first.
   We will coordinate the disclosure timeline with you.

---

## Module Security Violations

ScientificState uses a signed module system for domain plugins. If a domain module is found
to contain malicious code, a backdoor, or to violate the security contract, the following
revocation process applies:

- The module's `signed` flag is revoked in the module registry.
- The affected `module-manifest.json` version is tombstoned.
- An advisory is published listing the affected module ID, version range, and recommended action.
- Downstream installations are notified via the update channel.

For the full revocation flow, see **Main_Source.md §16.2 — Module Revocation**.

---

## TUF Key Compromise

ScientificState uses The Update Framework (TUF) for secure artifact distribution.
If a signing key is suspected to be compromised:

- Follow the key rotation procedure documented in **Main_Source.md §16.2 — TUF Key Compromise**.
- Report the suspected compromise immediately to security@scientificstate.org.
- Do not attempt key rotation without coordination with the core team.

---

## Scope

The following are **in scope** for security reports:

- `Core/daemon` — local execution daemon (FastAPI, IPC, file access)
- `Core/framework` — science kernel (data processing, state mutation)
- `Desktop` — Tauri desktop application (Rust + React, local file system access)
- Module signing and verification pipeline
- TUF update infrastructure

The following are **out of scope:**

- Vulnerabilities in third-party dependencies (report upstream; we will update our dependency)
- Issues requiring physical access to the user's machine
- Social engineering attacks

---

## Security Contacts

| Role             | Contact                               |
|------------------|---------------------------------------|
| Security reports | security@scientificstate.org          |
| GitHub Advisories| GitHub Security Advisory (preferred)  |
| Core team        | @scientificstate/core-team            |
