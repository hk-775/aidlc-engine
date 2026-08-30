# AIDLC launch materials draft

Status: working copy for a future alpha announcement. Do not publish without
the release checklist, governance approval, link replacement, and a fresh
security review.

## One-line description

AIDLC is a human-governed control plane for agent-assisted software delivery.

## Short description

AIDLC gives agents a bounded workflow for proposing work, submitting evidence,
and requesting lifecycle transitions while preserving human approval, risk,
and release authority. The alpha implementation runs locally with no runtime
dependencies and keeps a hash-linked JSON audit trail.

## Suggested announcement

We are sharing AIDLC 0.1.0 as an open-source evaluation candidate. It explores
a deliberately narrow question: how can teams gain useful agent assistance
without treating an agent proposal as delivery authority?

The repository includes a deterministic lifecycle, configurable evidence,
agent assignment scope, independent human gates, local integrity checks, a
synthetic demo, and an offline project site. It does not connect to
source-control or deployment systems and is not ready to protect production
decisions.

We welcome review of the policy model, threat assumptions, accessibility,
operational limitations, and clean-room provenance process.

## Demo talking points

1. Run the 32-event synthetic lifecycle.
2. Show an agent-proposed assignment approved by a person.
3. Show artifact metadata bound to that assignment.
4. Show a normal transition requiring independent human approval.
5. Show the design gate requiring a technical reviewer.
6. Show the release gate requiring two distinct human roles.
7. Show an agent release request failing closed.
8. Verify the complete audit hash chain.
9. End with the readiness ledger and limitations.

## Claims that are supportable

- No runtime Python dependencies.
- Offline local evaluation.
- Deterministic test and demo values.
- Human approval on every lifecycle transition.
- Mandatory role coverage on configured high-impact transitions.
- Tamper-evident hash chain for the stored event sequence.
- No external assets or telemetry in the static site.

## Claims to avoid

- Production ready, enterprise ready, highly available, or scalable.
- Immutable, unhackable, compliant, certified, or zero trust.
- Autonomous delivery, automated release, or risk elimination.
- Cryptographically authenticated actors or non-repudiation.
- Compatibility with a delivery tool that has not been tested.

## Assets

- Full logo: `site/assets/aidlc-logo.svg`
- Icon: `site/assets/aidlc-icon.svg`
- Architecture image: `site/assets/architecture.svg`
- Architecture source: `site/assets/architecture.dot`
- Static site: `site/`

## Required pre-publication edits

- Configure package and repository links after publication locations are final.
- Configure real repository ownership and reporting contacts.
- Confirm license and notice text with project counsel.
- Run all tests, scans, coverage, package checks, and the release checklist.
- Review screenshots and announcement copy for current behavior.
