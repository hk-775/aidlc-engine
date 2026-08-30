# Local runbook

## Purpose

Operate and troubleshoot one AIDLC project store during local evaluation.

## Start a project

```console
PYTHONPATH=src python3 -m aidlc \
  --store .aidlc-evaluation \
  init \
  --name "Evaluation project" \
  --description "Synthetic local run" \
  --actor-id human_owner \
  --actor-kind human \
  --role project_owner
```

Protect the directory with host filesystem permissions. Do not run as an
administrator.

## Routine checks

Before and after a workflow session:

```console
PYTHONPATH=src python3 -m aidlc \
  --store .aidlc-evaluation \
  verify-audit

PYTHONPATH=src python3 -m aidlc \
  --store .aidlc-evaluation \
  status
```

Treat any integrity failure as a stop condition. Preserve a copy for
investigation before attempting manual repair.

## Expected files

```text
.aidlc-evaluation/
  .aidlc.lock
  audit/
  policy.json
  state.json
```

A `.aidlc.pending.json` file indicates an interrupted transaction. The next
normal read or mutation attempts validated completion. Do not edit it.

## Common failures

### `not_found`

The store is not initialized, a supplied identifier is wrong, or a required
file is missing. Confirm `--store` and inspect status.

### `conflict`

State does not permit the operation. Common causes are open assignments,
missing deliverables, a pending proposal, wrong stage, or duplicate artifact.
Read the structured details.

### `authorization_error`

Actor kind, role, assignment, or independence does not meet the operation.
Do not work around this by changing an agent to a human actor.

### `integrity_error`

State, policy, audit files, or pending data are inconsistent. Stop mutations.
Record:

- command and time;
- full error JSON;
- directory listing;
- filesystem and operating system; and
- whether another process or manual edit touched the store.

### `persistence_error`

Check permissions, free space, path type, symbolic links, and filesystem
health. AIDLC rejects symbolic links for key storage paths.

## Safe backup for evaluation

There is no online backup command. For an offline evaluation copy:

1. stop all AIDLC processes using the store;
2. run `verify-audit`;
3. copy the complete directory with metadata preserved;
4. verify the copied directory separately; and
5. record the copied audit head hash outside both directories.

This is not a production backup strategy and does not prevent rollback.

## Restore test

Restore only into a new empty directory, then run:

```console
PYTHONPATH=src python3 -m aidlc \
  --store PATH_TO_RESTORED_COPY \
  verify-audit
```

Compare project identifier, event count, and head hash to the recorded values.

## Pending transaction response

If recovery succeeds, verify the audit and inspect the last event. If recovery
fails, do not delete the pending file or last event. Preserve the directory for
analysis. Version 0.1 has no supported repair tool.

## Disk growth

Audit events are never compacted. Monitor directory size manually. Start a new
evaluation project before storage becomes operationally inconvenient.

## End an evaluation

1. verify the audit;
2. export or record the final state and head hash if needed;
3. confirm no sensitive content was stored;
4. stop any local static-site server; and
5. remove the project directory only under the evaluator's data-retention
   process.
