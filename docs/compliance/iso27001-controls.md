# ISO 27001:2022 Annex A Control Mapping — ScientificState

## A.5 — Organizational Controls
| Control | Title | Applicability | Implementation |
|---------|-------|--------------|----------------|
| A.5.1 | Information security policies | Yes | Main_Source Constitutional Principles |
| A.5.2 | Information security roles | Yes | CODEOWNERS, institution roles (admin/researcher) |
| A.5.3 | Segregation of duties | Yes | Worker separation, path ownership |

## A.6 — People Controls
| Control | Title | Applicability | Implementation |
|---------|-------|--------------|----------------|
| A.6.1 | Screening | Partial | ORCID verification for researchers |
| A.6.2 | Terms of employment | N/A | Open-source project |

## A.7 — Physical Controls
| Control | Title | Applicability | Implementation |
|---------|-------|--------------|----------------|
| A.7.1-A.7.14 | Physical security | N/A | Cloud-native, no physical infrastructure |

## A.8 — Technological Controls
| Control | Title | Applicability | Implementation |
|---------|-------|--------------|----------------|
| A.8.1 | User endpoint devices | Yes | Desktop app security (Tauri sandbox) |
| A.8.2 | Privileged access rights | Yes | Supabase RLS, role-based access |
| A.8.3 | Information access restriction | Yes | RLS policies, institution-scoped data |
| A.8.5 | Secure authentication | Yes | SAML SSO, ORCID, Ed25519 |
| A.8.9 | Configuration management | Yes | Encrypted config files, env var override |
| A.8.10 | Information deletion | Yes | GDPR deletion workflow |
| A.8.11 | Data masking | Yes | Credential masking (length-only logging) |
| A.8.12 | Data leakage prevention | Yes | Localhost-only daemon, signed grants |
| A.8.16 | Monitoring activities | Yes | Health endpoints, federation monitoring |
| A.8.24 | Use of cryptography | Yes | AES-256 credentials, Ed25519 signatures |
| A.8.25 | Secure development lifecycle | Yes | Phase-gated, 1245+ tests, CI/CD |
| A.8.28 | Secure coding | Yes | Ruff linting, type checking, code review |

---
*Prepared for ISO 27001:2022 certification readiness — formal certification planned for Phase 9*
