# SOC 2 Type II Control Matrix — ScientificState

## Trust Services Criteria

### CC1 — Control Environment
| Control | Description | Implementation | Evidence |
|---------|------------|----------------|----------|
| CC1.1 | Management commitment to integrity | Code review policy, PR approval requirements | GitHub PR settings, CODEOWNERS |
| CC1.2 | Board oversight | Project governance documented in Main_Source | Main_Source.md |

### CC2 — Communication and Information
| Control | Description | Implementation | Evidence |
|---------|------------|----------------|----------|
| CC2.1 | Internal communication | GitHub Issues, PR reviews, phase documentation | Phase docs in 9 Constitutional Principles/ |

### CC3 — Risk Assessment
| Control | Description | Implementation | Evidence |
|---------|------------|----------------|----------|
| CC3.1 | Risk identification | Per-phase risk table in execution plans | Execution_Plan_Phase*.md risk sections |
| CC3.2 | Fraud risk | Immutable audit log, INSERT-only usage tracking | audit_log table, qpu_usage_log |

### CC5 — Control Activities
| Control | Description | Implementation | Evidence |
|---------|------------|----------------|----------|
| CC5.1 | Access control | Supabase RLS, ORCID-based auth, role enforcement | RLS policies, auth.jwt()->>'orcid' |
| CC5.2 | Logical access | Daemon localhost-only, encrypted credential storage | main.py localhost binding, credential.py |
| CC5.3 | Authentication | SAML SSO, ORCID verification, Ed25519 signatures | Web portal auth, federation trust |

### CC6 — Logical and Physical Access Controls
| Control | Description | Implementation | Evidence |
|---------|------------|----------------|----------|
| CC6.1 | Credential management | AES-256 encrypted local config, 600 permissions | ~/.scientificstate/qpu-credentials.json |
| CC6.2 | Token security | Length-only logging, no plaintext storage | credential.py, cost_gate.py |
| CC6.3 | QPU access control | BYOT + Institutional Broker, signed grants | qpu_admin.py, broker grant protocol |

### CC7 — System Operations
| Control | Description | Implementation | Evidence |
|---------|------------|----------------|----------|
| CC7.1 | Change management | Phase-gated development, CI/CD pipeline | phase*-ci.yml, justfile |
| CC7.2 | Monitoring | Daemon health check, federation health | /health endpoint, federation health API |
| CC7.3 | Incident response | Circuit-breaker pattern, graceful degradation | ibm_backend.py, ionq_backend.py |

### CC8 — Change Management
| Control | Description | Implementation | Evidence |
|---------|------------|----------------|----------|
| CC8.1 | Infrastructure changes | Supabase migrations, versioned schemas | Infrastructure/supabase/migrations/ |
| CC8.2 | Software changes | PR-based workflow, automated tests | CI pipeline, 1245+ tests |

### CC9 — Risk Mitigation
| Control | Description | Implementation | Evidence |
|---------|------------|----------------|----------|
| CC9.1 | Vendor management | QPU provider abstraction, BYOT model | quantum_hw backend architecture |
| CC9.2 | Business continuity | Fallback chain, in-memory fallback | orchestrator fallback, ReplicationEngine fallback |

## Data Protection
| Category | Control | Implementation |
|----------|---------|----------------|
| Encryption at rest | Database encryption | Supabase default encryption, SQLite WAL mode |
| Encryption in transit | TLS everywhere | HTTPS for Web, WSS for federation sync |
| Data classification | Scientific data | SSV 7-tuple structure, domain-agnostic core |
| Retention | Immutable records | INSERT-only audit_log, usage_log, price_snapshots |
| Privacy | GDPR compliance | Privacy settings, data export, deletion workflow |

## Audit Trail
- `audit_log` table: all state changes with actor, timestamp, action
- `qpu_usage_log`: immutable QPU usage records
- `qpu_price_snapshots`: immutable price versioning
- Federation sync log: cross-institutional data exchange records

---
*Prepared for SOC 2 Type II readiness — actual audit planned for Phase 9*
