# AI-DLC Engine launch materials draft

Status: publication-ready draft for the alpha repository. Do not announce or
change repository visibility until the exact commit has a fresh independent
security review, GitHub private vulnerability reporting is enabled, and the
publication checklist is complete.

## One-line description

The human-governed automation engine for the AI Development Lifecycle.

## Short description

AI-DLC Engine automates lifecycle state, evidence requirements, bounded work,
approval gates, and audit records while preserving human approval, risk, and
release authority. The alpha implementation runs locally with no runtime
dependencies and keeps a hash-linked JSON audit trail.

## Suggested announcement

We are sharing AI-DLC Engine 0.1.0 as an open-source evaluation candidate. It
explores a deliberately narrow question: how can teams automate the AI
Development Lifecycle without treating an agent proposal as delivery
authority?

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

- Repository: `https://github.com/hk-775/aidlc-engine`
- Project site: `https://hk-775.github.io/aidlc-engine/`
- Architecture explorer: `https://hk-775.github.io/aidlc-engine/architecture.html`
- Architecture explorer source: `site/architecture.html`
- Full logo: `site/assets/aidlc-engine-logo.svg`
- Icon: `site/assets/aidlc-engine-icon.svg`
- Architecture image: `site/assets/architecture.png`
- Editable architecture source: `site/assets/architecture.drawio`
- AWS reference architecture: `site/assets/aws-reference-architecture.png`
- Editable AWS reference source:
  `site/assets/aws-reference-architecture.drawio`
- Static-site architecture image: `site/assets/architecture.svg`
- Static-site vector source: `site/assets/architecture.dot`
- Static site: `site/`
- Publication artifact inventory: `docs/PUBLICATION_ARTIFACTS.md`

## Required pre-publication edits

- Confirm the exact commit has a fresh independent security review.
- Enable and test GitHub private vulnerability reporting.
- Confirm repository ownership, branch rules, topics, and Pages settings.
- Confirm license and notice text with project counsel.
- Run all tests, scans, coverage, package checks, and the release checklist.
- Review screenshots and announcement copy for current behavior.
