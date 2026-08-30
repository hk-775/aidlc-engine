# AI-DLC Engine quickstart

This guide runs AI-DLC Engine locally without installing runtime dependencies
or contacting a network service.

## 1. Check the environment

```console
python3 --version
```

Python 3.11 or newer is required. The local persistence layer uses POSIX file
locking.

## 2. Run the complete synthetic demo

```console
PYTHONPATH=src python3 -m aidlc_engine --store .tmp/quickstart-demo demo
```

Expected summary values:

- `"current_stage": "release"`
- `"event_count": 32`
- `"audit_valid": true`
- five artifacts, assignments, and proposals

The `release` stage is a recorded governance outcome. No repository merge,
deployment, publication, or production operation occurs.

## 3. Verify and inspect the store

```console
PYTHONPATH=src python3 -m aidlc_engine \
  --store .tmp/quickstart-demo \
  verify-audit

PYTHONPATH=src python3 -m aidlc_engine \
  --store .tmp/quickstart-demo \
  status

PYTHONPATH=src python3 -m aidlc_engine \
  --store .tmp/quickstart-demo \
  events
```

All commands emit JSON. Audit verification should report 32 events and a valid
head hash.

## 4. Observe a denied agent action

```console
PYTHONPATH=src python3 -m aidlc_engine \
  --store .tmp/quickstart-demo \
  guard-operation \
  --actor-id agent_builder \
  --actor-kind agent \
  --operation release
```

The command returns a nonzero status and a `forbidden_operation` error. Policy
files cannot enable that operation for agents.

## 5. Validate a stricter policy

```console
PYTHONPATH=src python3 -m aidlc_engine \
  validate-policy \
  --file examples/policy.strict.json
```

The example adds artifacts and human role coverage while preserving hard
safety controls.

## 6. Initialize a separate project

```console
PYTHONPATH=src python3 -m aidlc_engine \
  --store .tmp/manual-project \
  --id-seed manual-example \
  --fixed-time 2026-01-20T09:00:00Z \
  init \
  --name "Document intake pilot" \
  --description "Synthetic evaluator-created project" \
  --actor-id human_owner \
  --actor-kind human \
  --role project_owner
```

Continue with `propose-work`, `approve-work`, `add-artifact`,
`complete-work`, `propose-transition`, and `approve-transition`. Use
`python3 -m aidlc_engine <command> --help` for command-specific fields. Copy
generated assignment, artifact, and proposal identifiers from each JSON
result.

## 7. Run repository checks

```console
make test
make coverage
make scan
make package-check
```

Package archives are created only in ignored temporary storage and removed
after inspection.

## 8. View the offline project site

```console
make site
```

The static site reads only repository-local HTML, CSS, JavaScript, and SVG
files. It does not connect to the live demo store.
