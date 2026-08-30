# Architecture

## Purpose

AI-DLC Engine is a local automation engine for recording bounded agent work and
human delivery decisions across the AI Development Lifecycle. The architecture
favors inspectability and deterministic behavior over distribution,
integration breadth, or throughput.

Editable draw.io source:
[`../site/assets/architecture.drawio`](../site/assets/architecture.drawio)

README PNG:
[`../site/assets/architecture.png`](../site/assets/architecture.png)

Static-site vector source:
[`../site/assets/architecture.dot`](../site/assets/architecture.dot)

Static-site SVG:
[`../site/assets/architecture.svg`](../site/assets/architecture.svg)

## Components

### CLI

`aidlc_engine.cli` parses commands, constructs an asserted actor, invokes the
application service, and emits JSON. It maps expected errors to stable nonzero
exit codes. The CLI contains no integration client and makes no network calls.

### Lifecycle service

`aidlc_engine.service` owns user-visible operations:

- propose, approve, and complete work;
- register artifact metadata;
- propose, approve, and reject transitions;
- record a human risk-owner decision; and
- evaluate an operation against the authority boundary.

Validation happens again in the service even when the caller supplied a
schema-valid object. Every mutating operation runs as a repository callback
while the project lock is held.

### Policy validator

`aidlc_engine.policy` defines defaults and validates a complete policy object.
Unknown
fields fail validation. Safety controls are code invariants:

- every transition requires a human;
- proposer and approver are independent;
- high-impact gates cannot be removed or weakened below their minimum roles;
  and
- hard-denied agent operations must remain false.

Policy is set when a project is initialized. Version 0.1 does not support an
in-place policy migration. The canonical policy digest is bound into state so
manual policy edits are detected.

### Model and value layer

`aidlc_engine.models` contains stage order, actor rules, identifier patterns,
and state-shape checks. `aidlc_engine.values` provides production-local values or
deterministic identifiers and timestamps for tests and demonstrations.

### JSON repository

`aidlc_engine.persistence` stores one project in one directory. A POSIX
advisory lock serializes initialization, reads that verify integrity, and
mutations.

The durable files are:

```text
policy.json
state.json
audit/<sequence>-<event-id>.json
```

The lock file is operational. A pending transaction file exists only between
transaction preparation and completion. Their v1 filenames remain
`.aidlc.lock` and `.aidlc.pending.json` for compatibility with existing stores.

### Audit layer

`aidlc_engine.audit` canonicalizes JSON with sorted keys and compact separators.
Each event contains the previous hash, then hashes its own unsigned fields with
SHA-256. Verification checks:

- contiguous filenames and sequences;
- event identifier and filename agreement;
- event shape;
- previous-hash linkage;
- event content hash;
- project identifier consistency;
- event count; and
- final state head hash; and
- final state-content digest.

## Lifecycle state

Stages are fixed and adjacent:

```text
discovery -> requirements -> design -> implementation -> verification -> release
```

There is no backward or skipped transition in schema version 1. Rework is
represented by additional assignments, evidence, or a rejected proposal while
remaining in the current stage. This is intentionally simple and may not fit
every delivery process.

## Transaction sequence

For each mutation, the repository:

1. obtains the project lock;
2. completes a valid pending transaction, if one exists;
3. loads and validates policy and state;
4. verifies the full audit chain;
5. runs the service mutation against a deep copy;
6. creates the next canonical audit event;
7. writes event and next state to an atomic pending file;
8. creates the event file with exclusive-create semantics and flushes it;
9. atomically replaces `state.json` and flushes the directory;
10. removes the pending file and flushes the project directory; and
11. releases the lock.

Recovery replays only the already prepared event and state pair. If an event
file already exists, recovery requires exact content equality. An invalid
pending object fails closed.

## Trust boundaries

### Trusted for the local evaluation

- the Python interpreter;
- the local operating system and filesystem;
- the invoking process's actor assertions;
- repository source and active policy; and
- exclusive access discipline through the provided repository API.

### Not trusted or not provided

- agent claims of authority;
- artifact content based on metadata alone;
- host administrators;
- external delivery systems;
- remote identities;
- multi-host clocks; and
- copied stores without an external trust anchor.

## Safety properties

- Agents cannot call human-only service methods successfully.
- Agent governance roles are invalid at actor construction.
- Policy cannot enable hard-denied agent operations.
- Evidence and open assignments are checked both when a transition is proposed
  and when it is approved.
- Gate approvals use distinct actor identifiers and role coverage.
- A transition changes stage only in the same event that completes its gate.
- External execution actions have no implementation path.

## Failure behavior

Validation, authorization, conflict, integrity, missing-data, and persistence
failures have explicit types. A failed mutation writes no state or audit event.
Unexpected CLI exceptions are hidden behind a generic `internal_error` result
to avoid leaking local details.

## Scale characteristics

Every mutation and verified read scans the complete audit directory. This is
linear in event count and suitable only for small local evaluations. There is
no indexing, compaction, archival, or benchmark claim.

## Portability

The current lock implementation imports `fcntl`, so Windows is unsupported.
JSON data is portable, but filesystem atomicity and flush guarantees still
depend on the host and storage device.
