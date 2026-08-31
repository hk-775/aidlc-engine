# Production readiness

## Readiness statement

AI-DLC Engine 0.1.0 is suitable for local, synthetic evaluation. It is **not ready** to
authorize production software delivery. The ledger below separates implemented
evidence from unresolved work.

Status meanings:

- **Implemented**: present and covered by repository validation.
- **Partial**: useful local behavior with material gaps.
- **Missing**: no production-capable implementation.
- **Blocked**: must be resolved before production consideration.

## Readiness ledger

| Area | Status | Current evidence | Production gap |
| --- | --- | --- | --- |
| Lifecycle determinism | Implemented | Fixed adjacent stages and injected values | Migration and process customization strategy |
| Evidence policy | Implemented | Required types checked at proposal and approval | Trusted retrieval and content re-verification |
| Agent authority boundary | Implemented locally | Hard-denied policy and service checks | Authenticated workload identity |
| Human approval | Partial | Human kind, role, and separation checks | Verified identity, role lifecycle, revocation |
| High-impact gates | Implemented locally | Design and release role coverage | Organization-specific control mapping and assurance |
| Assignment scope | Implemented locally | Human approval and deliverable-bound submissions | Delegation expiry, reassignment, cancellation |
| Risk decision record | Partial | Human risk-owner record | Risk objects, expiry, mitigation, escalation |
| Atomic local persistence | Partial | Flush, replacement, lock, pending recovery | Supported database and fault certification |
| Audit integrity | Partial | Canonical hash chain and full verification | Signatures, external anchor, retention policy |
| Authentication | Missing / Blocked | None | Identity provider and secure sessions |
| Authorization administration | Missing / Blocked | CLI-asserted roles | Protected policy and role management |
| Confidentiality | Missing / Blocked | Local filesystem permissions only | Encryption, key management, data classification |
| Remote API | Missing | None | Authenticated, rate-limited service interface |
| Multi-user concurrency | Missing | One local advisory lock | Transactional distributed coordination |
| High availability | Missing | None | Replication, failover, recovery objectives |
| Backup and restore | Missing / Blocked | Manual file copy only | Tested backups, restore validation, rollback defense |
| Schema migration | Missing / Blocked | Version checks only | Forward and rollback migration tooling |
| Observability | Missing | CLI errors and files | Metrics, logs, traces, alerting, redaction |
| Incident response | Partial | Security policy and local runbook | On-call ownership, drills, forensic retention |
| Performance evidence | Missing | No benchmark | Workload model, targets, repeatable benchmark |
| Scalability | Missing | Linear audit verification | Indexing, archival, load and capacity tests |
| Supply-chain assurance | Partial | No runtime deps, pinned CI actions, uv-locked development tools, hash-pinned build subset, source/history scans, verified release archives | Signed releases, reproducible builds, provenance attestations |
| Security testing | Partial | Unit adversarial cases and scans | Independent review, fuzzing, fault injection |
| Accessibility | Partial | Semantic local site and automated source checks | Manual assistive-technology audit |
| Privacy | Partial | Synthetic defaults and warnings | Data inventory, retention, deletion, legal review |
| Compliance | Not claimed | None | Context-specific assessment by qualified parties |
| Support operations | Missing | Community documentation only | Staffing, service objectives, escalation |

## Blocking risks

1. Caller identity and role are unauthenticated.
2. A privileged local attacker can replace a complete valid-looking history.
3. The filesystem store has no tested backup, restore, or migration mechanism.
4. Advisory locking and full audit scans do not support distributed operation.
5. Artifact content is external and not revalidated by the control plane.
6. No production monitoring, incident ownership, or recovery objectives exist.
7. Security evaluation is repository-local, not independent assurance.

## Suggested maturation sequence

### Phase 1: evaluation hardening

- Add property and fuzz tests.
- Add crash injection around every persistence boundary.
- Define stored-schema compatibility rules.
- Perform manual accessibility and security reviews.
- Benchmark representative local histories.

### Phase 2: authenticated service prototype

- Introduce authenticated human and workload identity.
- Protect role and policy administration.
- Use a transactional database and append-only event model.
- Sign events and anchor checkpoints externally.
- Keep external delivery execution outside agent authority.

### Phase 3: operational validation

- Establish backup, restore, migration, monitoring, and incident procedures.
- Define service targets from measured workloads.
- Conduct independent security assessment.
- Pilot with non-production, low-sensitivity projects.

### Phase 4: production decision

A production decision should require documented acceptance by engineering,
security, operations, privacy, legal, and the accountable business owner. It
must not be inferred from repository checks alone.
