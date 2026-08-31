# Publication artifacts

## Purpose

This inventory defines the complete customer-facing artifact set for AI-DLC
Engine. It keeps the repository, project site, architecture material, evaluator
guides, and release archives aligned with the current implementation.

An artifact belongs in this set only when it can be maintained from repository
source and validated without private services or production credentials.

## Customer-facing set

| Artifact | Purpose | Canonical source |
| --- | --- | --- |
| Repository overview | Product boundary, fast evaluation, limitations, and document index | `README.md` |
| Guided evaluation | Install, demo, denied action, policy, and manual project workflow | `QUICKSTART.md` |
| Evaluator checklist | Supported environment, validation, smoke tests, and cautions | `STARTUP.md` |
| Project landing page | Public product summary and synthetic lifecycle status | `site/index.html` |
| Architecture explorer | Interactive lifecycle, governance, persistence, and trust-boundary walkthrough | `site/architecture.html` |
| Long-form architecture | Components, transaction sequence, trust boundaries, and scale limits | `docs/ARCHITECTURE.md` |
| Feature inventory | Implemented lifecycle and authority flows | `docs/FEATURES_AND_FLOWS.md` |
| Readiness ledger | Implemented evidence, production gaps, and blocking risks | `docs/PRODUCTION_READINESS.md` |
| Security material | Reporting policy, threat model, adversarial review, and responsible use | `SECURITY.md`, `docs/THREAT_MODEL.md`, `docs/ADVERSARIAL_REVIEW.md`, `docs/RESPONSIBLE_USE.md` |
| Launch copy | Supportable claims, claims to avoid, demo script, and asset locations | `launch-materials.md` |
| Browser evidence | Exact Pages-base, interaction, asset, network-isolation, and mobile checks in Chrome | `tools/browser_check.py` |
| Release evidence | Verified source and wheel archives with recorded SHA-256 digests | `.github/workflows/release.yml`, `tools/release_check.py` |

## Visual source of truth

The architecture has several representations for different consumers:

- `site/assets/architecture.drawio` is the editable diagram source.
- `site/assets/architecture.png` is the README and presentation render.
- `site/assets/architecture.svg` is the accessible vector used on the landing
  page.
- `site/assets/architecture.dot` is the compact logical graph source.
- `site/assets/aws-reference-architecture.drawio` is the editable proposed AWS
  deployment.
- `site/assets/aws-reference-architecture.png` is its presentation render.

The canonical visual identity files are:

- `site/assets/aidlc-engine-logo.svg`
- `site/assets/aidlc-engine-icon.svg`

The project site uses only repository-owned assets. It loads no remote fonts,
scripts, images, telemetry, or network APIs.

## Release inclusion

The source distribution must contain:

- the landing page and architecture explorer;
- both site JavaScript files and the shared stylesheet;
- both editable draw.io sources and both PNG renders;
- this publication inventory and the long-form architecture reference; and
- the locked development environment and browser/release verification tooling.

`tools/package_check.py` and `tools/release_check.py` enforce those members.

## Validation

Before publication or announcement, run:

```console
make sync
make check
```

The Chrome check serves the site beneath `/aidlc-engine/`, exercises both
pages and their controls, verifies all six architecture downloads, confirms
the current and AWS reference images load, and rejects external requests,
API calls, WebSockets, browser exceptions, failed loads, and mobile overflow.
For transient visual-review captures, run:

```console
uv run --locked --all-groups python tools/browser_check.py \
  --screenshot-dir /tmp/aidlc-engine-browser
```

## Intentional omissions

AI-DLC Engine version 0.1 does not include container images, cloud deployment
templates, production evidence bundles, service dashboards, or signed runtime
artifacts. The implementation is a local evaluation engine with no remote API
or external delivery integration, so publishing those artifacts would imply a
deployment surface that does not exist.

Runtime dependencies are empty. `uv.lock` is the canonical reproducible
development environment, including browser validation. The build and coverage
subset remains independently versioned and hash-pinned in
`requirements-build.lock` for auditability.
