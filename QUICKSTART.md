# AI-DLC Engine quickstart

This guide installs AI-DLC Engine with `uv` and runs it locally without runtime
dependencies.

## 1. Check the environment

```console
uv --version
```

`uv` must have access to Python 3.11 or newer, either locally or through its
managed Python support. The persistence layer uses POSIX file locking.

## 2. Install the command

From the repository root:

```console
uv tool install .
```

This creates an isolated tool environment and exposes the `aidlc-engine`
command.

## 3. Run the complete synthetic demo

```console
aidlc-engine --store .tmp/quickstart-demo demo
```

Expected summary values:

- `"current_stage": "release"`
- `"event_count": 32`
- `"audit_valid": true`
- five artifacts, assignments, and proposals

The `release` stage is a recorded governance outcome. No repository merge,
deployment, publication, or production operation occurs.

## 4. Verify and inspect the store

```console
aidlc-engine \
  --store .tmp/quickstart-demo \
  verify-audit

aidlc-engine \
  --store .tmp/quickstart-demo \
  status

aidlc-engine \
  --store .tmp/quickstart-demo \
  events
```

All commands emit JSON. Audit verification should report 32 events and a valid
head hash.

## 5. Observe a denied agent action

```console
aidlc-engine \
  --store .tmp/quickstart-demo \
  guard-operation \
  --actor-id agent_builder \
  --actor-kind agent \
  --operation release
```

The command returns a nonzero status and a `forbidden_operation` error. Policy
files cannot enable that operation for agents.

## 6. Validate a stricter policy

```console
aidlc-engine \
  validate-policy \
  --file examples/policy.strict.json
```

The example adds artifacts and human role coverage while preserving hard
safety controls.

## 7. Initialize a separate project

```console
aidlc-engine \
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
`aidlc-engine <command> --help` for command-specific fields. Copy generated
assignment, artifact, and proposal identifiers from each JSON result.

## 8. Run repository checks

```console
make test
make coverage
make scan
make package-check
```

Package archives are created only in ignored temporary storage and removed
after inspection.

## 9. View the offline project site

```console
make site
```

The static site reads only repository-local HTML, CSS, JavaScript, and SVG
files. It does not connect to the live demo store.
