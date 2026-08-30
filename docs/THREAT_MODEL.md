# Threat model

## Scope

This model covers the local alpha implementation: CLI, lifecycle service,
policy validation, JSON state, pending transaction, and event directory on one
POSIX host.

## Assets

- Correct lifecycle stage.
- Active policy and its binding to state.
- Artifact and assignment metadata.
- Transition proposals and human approvals.
- Risk decision records.
- Audit sequence and head hash.
- Availability of the local project store.
- Project contributor provenance.

## Actors

- Human caller asserting an identifier and roles.
- Agent caller asserting an identifier.
- Local evaluator operating the host.
- Malicious local process with some filesystem access.
- Host administrator with full control.
- Contributor proposing repository changes.

## Trust assumptions

- Python and the operating system behave as documented.
- The project directory is on a filesystem that supports atomic replacement
  and durable flush semantics closely enough for local evaluation.
- Cooperative writers use the repository lock.
- The evaluator protects the host account.
- The invoking environment supplies truthful human identity and role claims.

The last assumption is a major alpha limitation.

## Threats and controls

### Agent escalates authority

Threat: an agent requests approval, merge, deployment, release, risk
acceptance, gate satisfaction, or bypass.

Controls:

- actor-kind checks in human-only methods;
- agent governance roles rejected at actor creation;
- hard-denied operation set;
- policy constants forced false;
- generic guard denial; and
- no external execution implementation.

Residual risk: a malicious embedding environment can mislabel an agent as a
human because identity is not authenticated.

### Agent self-assigns unrestricted work

Threat: an agent creates authority by assigning itself broad work.

Controls:

- agent work starts as proposed;
- a distinct human approves it;
- artifacts are scoped to active assignment and deliverable type by default;
  and
- stage remains unchanged until separate transition approval.

Residual risk: a careless human can approve overly broad work.

### Evidence substitution

Threat: referenced evidence is absent, stale, from another stage, or altered
outside the control plane.

Controls:

- current-stage artifact identifier checks;
- type coverage at proposal and approval;
- stored SHA-256 digest; and
- duplicate detection for stage/type/digest.

Residual risk: AIDLC does not retrieve or re-hash external artifact content.
The caller must independently verify that content still matches the digest.

### Gate bypass through configuration

Threat: policy removes human approval or mandatory roles.

Controls:

- exact-key validation;
- mandatory true transition controls;
- mandatory high-impact gate presence, roles, and minimums; and
- denied agent permissions fixed false.

Residual risk: source code can be modified. Release provenance and binary
verification are not yet provided.

### Self-approval or role collapse

Threat: a proposer approves its own transition or one actor fills multiple
required approvals.

Controls:

- proposer identifier cannot approve;
- an actor can approve once per proposal; and
- each named role is represented once.

Residual risk: separate unauthenticated identifiers may represent one real
person.

### Audit tampering

Threat: event modification, deletion, insertion, or reordering.

Controls:

- exclusive event creation;
- read-only event file mode;
- contiguous filename checks;
- canonical content hashes;
- previous-hash chain;
- state count, head, and content-digest binding; and
- full verification before mutations.

Residual risk: a privileged attacker can replace state, policy, and the entire
event history consistently. There is no signature or external anchor.

### Interrupted write

Threat: process or host stops between audit and state persistence.

Controls:

- prepared pending pair;
- file and directory flushes;
- idempotent event append;
- atomic state replacement; and
- fail-closed recovery validation.

Residual risk: storage hardware or filesystem behavior can violate assumptions.
No fault-injection certification has been performed.

### Concurrent writer

Threat: two processes mutate the same project simultaneously.

Controls:

- POSIX advisory exclusive lock around verified reads and writes.

Residual risk: a process that ignores the lock can corrupt or race the store.
Network filesystems may have different semantics.

### Path and link abuse

Threat: a storage or artifact path redirects access outside the intended
location.

Controls:

- key storage paths reject symbolic links;
- event creation uses no-follow where available;
- artifact locators must be safe relative paths; and
- the core never opens artifact locators.

Residual risk: callers can deliberately choose a project root anywhere they
can write. Deployment wrappers must constrain allowed roots.

### Secret exposure

Threat: credentials enter source, examples, CLI output, or stored metadata.

Controls:

- credential-pattern repository scan;
- synthetic examples;
- no network integrations; and
- documentation warnings.

Residual risk: CLI users can still place secrets in titles, descriptions, or
rationales. There is no content classifier or encryption.

### Denial of service

Threat: very large state, audit history, or input slows every verification.

Controls:

- input length limits;
- configurable collection limits; and
- local single-writer scope.

Residual risk: audit verification is linear and event payload size has no
aggregate storage quota.

## Out of scope

- Compromised Python runtime or kernel.
- Full host administrator.
- Physical media attacks.
- External system authorization.
- Social engineering of reviewers.
- Legal or regulatory sufficiency.

## Security work required before production

See the blocking items in
[`PRODUCTION_READINESS.md`](PRODUCTION_READINESS.md).
