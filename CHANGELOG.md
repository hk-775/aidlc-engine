# Changelog

All notable changes to this project are documented here. The format follows the
principles of Keep a Changelog, and versions use semantic versioning.

## [Unreleased]

### Changed

- Rename the project from AIDLC to AI-DLC Engine, including the `aidlc-engine`
  distribution and CLI, `aidlc_engine` Python package, project site, and
  repository metadata.
- Use `.aidlc-engine` as the default local store while retaining the v1
  `.aidlc.lock` and `.aidlc.pending.json` filenames for store compatibility.

### Added

- Canonical repository, documentation, issue, security, and project-site
  metadata.
- Root ownership rules, private security-reporting links, and explicit
  bootstrap governance.
- Reachable Git history scanning for credential and provenance markers.
- Verified annotated-tag release artifacts with recorded SHA-256 digests.
- Manual Pages deployment constrained to the reviewed public `main` branch.

### Security

- Pin GitHub Actions to full commit identifiers and disable persisted checkout
  credentials.
- Pin CI runners to Ubuntu 24.04 and validate workflow hardening in repository
  scans.
- Hash-lock the complete build and coverage toolchain used by CI and releases.
- Restrict Pages write and OIDC permissions to its deployment job.
- Validate complete persisted records and audit actor values.
- Normalize local storage directory and event-file permissions.

### Fixed

- Keep repository scan selection compatible with Python 3.11.
- Avoid configuring an unused pip cache in dependency-free CI jobs.
- Install a pinned packaging toolchain before no-isolation package checks.
- Include build output in failed package-check diagnostics.
- Reject ambiguous or control-character artifact locators without internal
  errors.
- Correct publication metadata status in the adversarial review.

### Planned

- Gather evaluator feedback on policy ergonomics and audit exports.
- Define a migration approach before changing stored schema version 1.
- Evaluate authenticated service boundaries without expanding agent authority.

## [0.1.0] - 2026-08-30

### Added

- Deterministic six-stage lifecycle core.
- Configurable evidence requirements and additive human gates.
- Agent work proposal, human assignment approval, scoped artifact submission,
  and completion checks.
- Independent human transition approval with mandatory high-impact role
  coverage.
- Hard-denied agent operations enforced by validation and service code.
- Atomic local JSON state, pending-write recovery, advisory locking, and
  append-only hash-linked audit event files.
- Machine-readable command-line interface and deterministic synthetic demo.
- JSON Schemas, local static site, original SVG identity assets, and
  architecture source.
- Standard-library tests, coverage configuration, repository scans, temporary
  package validation, and CI workflows.
- Open-source governance, security, operations, product, and readiness
  documentation.

### Security

- Default-deny agent authority for merge, deployment, release, risk acceptance,
  transition approval, human-gate satisfaction, and gate bypass.
- Local site content policy and external-asset scan.
- Credential-pattern and provenance-boundary scans.
