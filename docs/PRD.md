# Product requirements document

## Product

AIDLC: AI Development Lifecycle.

## Status

Open-source alpha for local evaluation.

## Problem

Agent-assisted software work can produce proposals and artifacts faster than
teams can establish evidence, authority, and accountability. A chat transcript
or task completion signal does not prove that required reviews occurred or
that a person accepted the impact of a lifecycle transition.

## Product statement

AIDLC is a human-governed control plane that records agent work, evidence,
transition proposals, independent approvals, and a locally verifiable audit
sequence without granting agents delivery authority.

## Users

- Engineers evaluating coding or delivery agents.
- Technical reviewers responsible for design quality.
- Release and risk owners who need explicit gate records.
- Security and governance practitioners assessing authority boundaries.
- Open-source reviewers studying a small reference implementation.

## Goals for 0.1

1. Provide a deterministic six-stage workflow.
2. Require configurable evidence before progress.
3. Scope agent artifact submissions to approved work by default.
4. Permit agents to propose progress but never approve it.
5. Require human role coverage at high-impact transitions.
6. Fail closed when policy attempts to weaken fixed controls.
7. Persist a local project safely enough for repeatable evaluation.
8. Detect common audit deletion, insertion, reordering, and modification.
9. Produce useful JSON CLI results and explicit errors.
10. Ship documentation, tests, scans, schemas, and an offline demo.

## Non-goals for 0.1

- Connecting to a code host, build system, deployment platform, or cloud
  account.
- Executing merges, deployments, releases, rollbacks, or risk acceptance on
  behalf of an agent.
- Authenticating users or agents.
- Serving a multi-user remote API.
- Providing a database, high availability, or horizontal scale.
- Certifying compliance or replacing professional risk judgment.
- Storing artifact content.
- Supporting arbitrary process graphs.

## Functional requirements

### Lifecycle

- Stage order is fixed and transitions are adjacent.
- `release` is terminal.
- Only a completed approval flow changes stage.

### Evidence

- Policy names required artifact types by source stage.
- Artifact metadata contains type, title, digest, locator, assignment,
  submitter, and timestamp.
- Transition proposal and approval both recheck evidence.

### Work assignments

- An agent can propose work only for itself.
- A separate human approves proposed work.
- Agent artifact submission requires an active matching assignment by default.
- Completion requires every declared deliverable type.

### Human gates

- Every transition requires independent human approval.
- Design-to-implementation requires technical review.
- Verification-to-release requires distinct release and risk role coverage.
- Policy can add or strengthen gates.

### Agent restrictions

- Hard-denied operations remain false in every valid policy.
- Service methods reject agents at human-only boundaries.
- The CLI reports denial with a stable code and nonzero status.

### Audit and persistence

- Each state mutation creates one canonical hash-linked event.
- Event files use exclusive creation.
- State replacement is atomic.
- A pending transaction can be completed after interruption.
- Full-chain verification runs before state mutation.

## Quality requirements

- Python 3.11 through 3.13.
- No runtime dependencies.
- Standard-library tests.
- Branch coverage measured locally.
- Repository safety and hygiene scans.
- Static UI operable with keyboard and without external assets.
- Original, synthetic, industry-neutral examples.

## Success criteria for evaluation

- The synthetic demo completes with the expected deterministic counts.
- All specified agent actions are denied in code and CLI.
- Policy weakening attempts are rejected.
- Audit tampering tests fail verification.
- A clean copy passes tests, scans, package inspection, and demo workflow
  offline.

## Open questions

- Should future versions model rework with explicit backward transitions or
  stage-local iterations?
- How should authenticated actor identity bind to audit signatures?
- Which policy migrations can be made safely without changing prior evidence?
- What event anchoring model is appropriate for independent verification?
- Which integrations can remain proposal-only without becoming an execution
  path?
