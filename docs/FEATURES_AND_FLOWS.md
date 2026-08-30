# Features and flows

## Lifecycle overview

```text
discovery
  -> requirements
  -> design
  -> implementation
  -> verification
  -> release
```

Each arrow represents a proposal plus human approval, not automatic progress.

## Feature: work assignment

1. An agent or human proposes an assignment for the current stage.
2. An agent proposer can name only itself as assignee.
3. A different human approves the assignment.
4. The assignment becomes active.
5. The assignee submits every declared artifact type.
6. The assignee marks the work complete.

An assignment remains stage-bound. An active or proposed assignment can block a
transition when that policy control is enabled.

## Feature: evidence registration

Artifact content remains outside AIDLC. The registry records:

- synthetic identifier;
- current lifecycle stage;
- policy-facing artifact type;
- human-readable title;
- SHA-256 digest;
- safe relative locator;
- optional assignment identifier;
- submitter identity; and
- timestamp.

An agent's artifact must fit its active assignment when the default policy
control is enabled. A person can register evidence without an assignment, but
that identity is still only an assertion from the local caller.

## Feature: transition proposal

1. The caller requests the next adjacent stage.
2. AIDLC rejects terminal, skipped, or concurrent proposals.
3. The proposal must reference current-stage evidence.
4. Referenced artifacts must cover every policy-required type.
5. Open assignments are checked.
6. The proposal records its gate requirements.

Agents and humans can propose, subject to policy. Proposal is never approval.

## Feature: ordinary human approval

For a transition without a named role gate:

1. a human other than the proposer approves;
2. AIDLC rechecks evidence and open assignments; and
3. the same transaction records approval and changes the stage.

## Feature: high-impact gate

For design-to-implementation, a human holding `technical_reviewer` must approve.

For verification-to-release:

1. one human holding `release_manager` approves;
2. the proposal remains pending;
3. a different human holding `risk_owner` approves; and
4. only then does the stage become `release`.

One person cannot represent both approvals because duplicate actor approval is
rejected. Policy can add roles or raise the minimum count.

## Feature: rejection

A human can reject a pending transition with a reason. The project remains in
its current stage. A later proposal can reference revised evidence.

## Feature: risk record

A human with `risk_owner` can record a risk acceptance note. This feature does
not execute a release or override a gate. Agents cannot call it.

## Feature: audit verification

`verify-audit` reads every event in order and verifies the chain against
current state. Verification fails on:

- missing or extra files;
- a sequence gap;
- filename and event mismatch;
- changed event content;
- a broken previous hash;
- another project identifier; or
- a state head mismatch.

## Feature: deterministic evaluation

An embedding environment can inject a deterministic provider. The CLI exposes
this through `--id-seed` and `--fixed-time`, which must be supplied together.
Identifiers derive from seed, event sequence, and operation discriminator.
Timestamps increment by one microsecond per audit event.

## Feature: recovery

Before committing an event and state snapshot, AIDLC atomically stores the pair
as a pending transaction. A later operation completes that exact pair after an
interruption. Invalid pending data is not guessed or discarded.

## Machine-readable errors

Representative error codes:

- `validation_error`
- `human_actor_required`
- `forbidden_operation`
- `self_approval_forbidden`
- `evidence_requirements_unsatisfied`
- `open_assignments_block_transition`
- `mandatory_gate_missing`
- `unsafe_agent_permission`
- `integrity_error`

Error details are context, not a stable natural-language API.
