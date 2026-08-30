# Evaluation and startup guide

Use this sequence to evaluate the repository from a clean local copy.

## Supported evaluation environment

- POSIX host
- Python 3.11, 3.12, or 3.13
- Writable repository directory
- No network connection required

The package has no runtime dependencies. Coverage and the Python build frontend
are development tools; the core and tests use the standard library.

## Baseline validation

From the repository root:

```console
make check
make coverage
```

`make check` runs the test suite, nine repository scans, the complete
deterministic demo, and a temporary source/wheel build inspection. A successful
demo reaches the terminal lifecycle stage with a valid 32-event audit chain.

If Make is unavailable, run:

```console
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 tools/repo_scan.py --pretty
PYTHONPATH=src python3 tools/demo_check.py
PYTHONPATH=src python3 tools/package_check.py
```

## Manual smoke test

```console
PYTHONPATH=src python3 -m aidlc_engine --store .tmp/startup-demo demo
PYTHONPATH=src python3 -m aidlc_engine --store .tmp/startup-demo verify-audit
PYTHONPATH=src python3 -m aidlc_engine --store .tmp/startup-demo status
```

Confirm:

- the current stage is `release`;
- audit verification is true;
- state revision is 31;
- event count is 32;
- the policy digest is a 64-character lowercase hash; and
- no pending transaction file remains.

## Safety smoke test

```console
PYTHONPATH=src python3 -m aidlc_engine \
  --store .tmp/startup-demo \
  guard-operation \
  --actor-id agent_builder \
  --actor-kind agent \
  --operation deploy
```

Expected result: nonzero exit status and a machine-readable denial. Repeat with
`merge`, `release`, `accept_risk`, `approve_transition`,
`satisfy_human_gate`, and `bypass_gate` if desired.

## Static site

```console
make site
```

Use a browser or accessibility tool against the local address printed by
Python. The page remains useful with scripts disabled, except that the compact
demo metrics are not populated.

## Storage cleanup

Evaluation data is written only to the store path provided on the command line.
Paths under `.tmp/`, `.aidlc-engine/`, `.aidlc-engine-*`, the legacy
`.aidlc/` and `.aidlc-*` patterns, `demo-data/`, and `local-data/` are ignored.
Remove a demo directory only after confirming it contains no needed audit
record.

## Review entry points

- Product intent: [docs/PRD.md](docs/PRD.md)
- Core design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Policy model: [docs/CONFIGURATION.md](docs/CONFIGURATION.md)
- Threat analysis: [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md)
- Readiness ledger:
  [docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md)
- Local operations: [docs/LOCAL_RUNBOOK.md](docs/LOCAL_RUNBOOK.md)

## Evaluation cautions

Do not treat command-line actor fields as authenticated identity. Do not store
secrets, regulated records, private keys, or production evidence in the local
demo. Do not use the audit hashes as signatures or non-repudiation evidence.
