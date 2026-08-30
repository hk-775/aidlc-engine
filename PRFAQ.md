# AI-DLC Engine PRFAQ

Draft product narrative for discussion. It is not a launch commitment.

## Press release

### AI-DLC Engine automates the AI Development Lifecycle while keeping authority human

Software teams evaluating coding agents often face a control problem: useful
agent work arrives faster than the evidence and decisions needed to govern it.
AI-DLC Engine is an open-source automation engine that separates proposal from
authority. It automates lifecycle state, evidence requirements, bounded work,
approval gates, and audit records. Agents can prepare assigned work and
propose the next lifecycle stage. People approve transitions, represent
required review roles, and retain risk and release decisions.

The first alpha release focuses on inspectability. Its standard-library Python
core runs on one local host, stores JSON, applies deterministic policies, and
maintains a hash-linked audit trail. It does not connect to delivery systems or
claim production readiness.

The included synthetic workflow lets evaluators see evidence requirements,
assignment scope, independent approval, a two-role release gate, and integrity
verification without sharing data or configuring external services.

## Frequently asked questions

### What problem does AI-DLC Engine solve?

It provides a small governance state machine around agent-assisted software
work. The system records what was assigned, what evidence was submitted, who
proposed progress, which human approved it, and whether the audit chain remains
intact.

### Is this an autonomous delivery platform?

No. AI-DLC Engine intentionally does not merge, deploy, publish, or operate
production systems. It records bounded workflow decisions.

### Can an agent approve its own proposal?

No. The core requires human transition approval and rejects matching proposer
and approver identities. High-impact gates also require specific human role
coverage.

### Can policy configuration remove the human controls?

No. Configurations that grant hard-denied agent powers, remove required gates,
or disable independent human approval are invalid.

### What evidence does AI-DLC Engine store?

It stores artifact metadata, a SHA-256 digest, an optional safe relative
locator, the submitting actor, and the related assignment. It does not copy or
host artifact content.

### Is the audit trail immutable?

The application only appends new event files and verifies a hash chain. A host
administrator can still alter or replace files. Hashes reveal many forms of
tampering but do not prevent them and are not digital signatures.

### Who is the initial audience?

Engineers, security reviewers, governance practitioners, and product teams
evaluating how human decisions can bound agent-assisted delivery.

### What is required before production use?

At minimum: authenticated identity, durable role administration, signed or
externally anchored events, a supported database, backup and recovery, schema
migrations, multi-process and multi-host testing, security review, operational
monitoring, incident procedures, and integration-specific authorization.

### How is the project licensed?

Apache License 2.0.
