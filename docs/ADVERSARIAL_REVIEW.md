# Adversarial review

This review asks how the current design could fail under hostile or careless
use. It is a design exercise, not a completed penetration test.

## Review method

The review considered authority escalation, policy weakening, identity
confusion, evidence substitution, filesystem tampering, transaction
interruption, input abuse, user-interface supply chain, and misleading product
claims. Findings are categorized as blocked, partially mitigated, or open.

## Findings

### AR-01: Caller labels an agent as a human

Status: **open, production blocker**

The CLI trusts `--actor-kind`, identifier, and role arguments. A caller can
assert a human identity and invoke human-only methods.

Existing mitigation: the limitation is explicit, and no network service is
present.

Required work: authenticated identities, protected service credentials,
role administration, revocation, session binding, and audit signatures tied to
the authenticated principal.

### AR-02: Agent enables release permission in policy

Status: **blocked**

Policy validation requires every hard-denied agent operation to remain false.
The service also rejects those operations based on actor kind.

Defense depth: configuration, service, CLI, tests, schema, and repository scan.

### AR-03: Agent proposes and approves the same transition

Status: **blocked for correctly typed actors**

Approval requires a human actor, and matching proposer identity is rejected.
High-impact gates require human roles and distinct approval identities.

Residual issue: AR-01 allows identity misrepresentation.

### AR-04: One human fills two release roles

Status: **blocked by identifier**

Each actor can approve a proposal once. Required roles therefore need distinct
actor identifiers.

Residual issue: two identifiers are not proven to represent two people.

### AR-05: Evidence is deleted after proposal

Status: **partially mitigated**

The artifact record is in project state and is rechecked at approval. External
artifact content is not managed, so its locator can disappear or content can
change. The digest enables independent checking but AI-DLC Engine does not perform it.

Required work: content-addressed storage integration or an approval-time
verifier with a trusted evidence boundary.

### AR-06: Audit event is edited

Status: **detected**

Canonical hash verification fails. A state mutation will not proceed.

Residual issue: a privileged attacker can rewrite the complete history and
state consistently.

### AR-07: Last audit event is deleted with state rollback

Status: **not independently detectable**

The local store has no external checkpoint. A consistent rollback can appear
valid.

Required work: signed checkpoints or regular anchoring to an independently
controlled log.

### AR-08: Crash after event creation

Status: **recoverable by design, incompletely proven**

The pending transaction contains the exact next event and state. Recovery
accepts an existing event only if content is identical, then writes state.

Required work: systematic process-kill and filesystem fault-injection tests
across supported filesystems.

### AR-09: Rogue process ignores advisory lock

Status: **open**

Advisory locking coordinates cooperative AI-DLC Engine processes, not arbitrary
writers.

Required work: move production state behind a transactional service or
database with authenticated access.

### AR-10: Symbolic-link redirection

Status: **partially mitigated**

The project root, lock, audit directory, and read paths reject symbolic links.
Lock and JSON reads use no-follow where supported, event creation is exclusive,
and the project and audit directories are normalized to owner-only access.
Race-free traversal of every ancestor component is not formally established.

Required work: descriptor-relative file operations, dedicated storage
directory ownership, and platform-specific security testing.

### AR-11: Huge rationale exhausts storage

Status: **partially mitigated**

Individual text fields and collection counts are bounded. Total event storage,
number of risk decisions, and long-term audit growth are not quota-managed.

Required work: aggregate quotas, monitoring, archival, and backpressure.

### AR-12: Static site loads compromised third-party code

Status: **blocked in source**

The site uses local HTML, CSS, JavaScript, and SVG only. A scanner rejects
network-loaded assets and browser network APIs. A restrictive content policy
is present.

Residual issue: a hosting workflow or operator can modify published output.

### AR-13: Package metadata implies a real service

Status: **mitigated by configured links and validation**

Project URLs identify the intended repository, documentation, issue tracker,
site, changelog, and security policy. Repository scans and the release and
white-label checklists require operators to review them before publishing.

### AR-14: Hash chain is described as immutable

Status: **mitigated in documentation**

Repository material consistently describes the chain as tamper-evident, not
tamper-proof, signed, or non-repudiable.

## Abuse cases retained for regression tests

- Agent requests every hard-denied operation.
- Policy flips each denied operation to true.
- Policy removes or weakens each mandatory gate.
- Agent claims a governance role.
- Proposer attempts self-approval.
- Same approver attempts a second role.
- Approval references missing or wrong-stage evidence.
- Transition proceeds while assigned work is open.
- Event content, order, filename, count, and head are changed.
- Static content references a network asset.
- Source contains credential-like material or a blocked provenance label.

## Conclusion

The implementation provides meaningful local guardrails against correctly
typed agent callers and accidental audit modification. Authenticated identity,
externally anchored integrity, hardened storage, and production operations
remain unresolved blockers.
