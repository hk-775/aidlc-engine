# Configuration

## Policy file

A project receives one complete JSON policy at initialization. The active
policy is validated, canonicalized, hashed, and stored beside state. Manual
edits cause an integrity failure. Version 0.1 has no in-place policy update or
migration command.

Validate a policy before use:

```console
aidlc-engine \
  validate-policy \
  --file examples/policy.strict.json
```

Schema: [`../schemas/policy.schema.json`](../schemas/policy.schema.json)

## Required artifacts

`required_artifacts` has exactly one array for every lifecycle stage. Values
are policy-facing type identifiers such as `solution_design`.

```json
{
  "required_artifacts": {
    "discovery": ["opportunity_brief"],
    "requirements": ["delivery_requirements"],
    "design": ["solution_design"],
    "implementation": ["implementation_record"],
    "verification": ["verification_report"],
    "release": []
  }
}
```

The complete object also needs every other top-level policy field. Unknown
stage names and duplicate artifact types are invalid.

Required evidence applies when leaving a stage. `release` is terminal, so its
default requirement list is empty.

## Human gates

Keys are adjacent transitions:

```json
{
  "requirements->design": {
    "required_roles": ["project_owner"],
    "minimum_approvals": 1
  }
}
```

Every required role must be represented by an approval, and the total approval
count must meet the minimum. Each approving actor can approve a proposal once.

Two controls are mandatory:

- design-to-implementation includes technical review; and
- verification-to-release includes separate release and risk roles.

A policy can add roles, increase approval counts, or add gates to other
adjacent transitions. It cannot remove or weaken the mandatory controls.

## Agent permissions

The complete permission object names every recognized agent operation.
Proposal-oriented capabilities can be disabled. Authority-bearing operations
must remain false.

```json
{
  "agent_permissions": {
    "propose_work": true,
    "submit_artifact": true,
    "complete_assigned_work": true,
    "propose_transition": true,
    "merge": false,
    "deploy": false,
    "release": false,
    "accept_risk": false,
    "approve_transition": false,
    "satisfy_human_gate": false,
    "bypass_gate": false
  }
}
```

Changing a hard-denied value to true invalidates the full policy.

## Transition controls

`require_independent_approval` and
`require_human_approval_for_all_transitions` must remain true.

`block_with_open_assignments` is configurable. When true, a proposed or active
current-stage assignment blocks proposal and approval. Completed work does not.

## Artifact controls

The only supported digest algorithm is SHA-256.

`agent_submission_requires_active_assignment` can be disabled for an
experiment, but doing so weakens assignment scope. Human approval of stage
transitions still applies.

## Limits

Local collection limits bound:

- total artifacts;
- proposed plus active assignments; and
- pending transition proposals.

The implementation also allows only one pending transition proposal at a time,
even if the configured numeric limit is higher. The numeric limit reserves
future compatibility and still prevents an unsafe low-level state expansion.

## Actor configuration

Actors are command inputs, not policy entries:

```text
--actor-id human_reviewer
--actor-kind human
--role technical_reviewer
```

Identifiers use lowercase letters, digits, underscores, and hyphens. Agents
cannot claim built-in governance roles. In this alpha, no identity provider
attests to the actor fields.

## Deterministic values

Use both options together:

```text
--id-seed evaluation-1
--fixed-time 2026-01-15T12:00:00Z
```

Do not use a deterministic provider to claim real-world event time or identity.
