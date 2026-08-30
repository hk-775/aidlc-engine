# Clean-room provenance

## Purpose

This record explains how the AIDLC open-source candidate was produced while
avoiding reuse of provenance-sensitive material.

## Source boundary

Construction used only:

- the product and repository requirements supplied for this task;
- standard Python language and operating-system interfaces;
- common, generic software-engineering concepts such as state machines,
  role-based approvals, atomic file replacement, JSON Schema, and hash chains;
  and
- original synthetic examples and original project prose and graphics.

A separate planning and review pass used the user-designated source in
read-only mode. Inspection was limited to path metadata, package metadata, and
broad capability categories such as lifecycle orchestration, governance,
local persistence, command-line operation, user interface, observability, and
testing. A path-level personal marker was recorded only for denylist coverage.
No implementation content was copied into the construction context.

The implementation agent did not inspect external product repositories.
Reference repositories were reviewed only at the file-category level to
identify conventional open-source artifact classes. No source code, tests,
identifiers, prose, diagrams, policies, configuration, examples, branding,
personal artifacts, or collateral were imported, adapted, translated, or
mechanically transformed.

## Independent construction

The implementation was designed from first principles around these public
concepts:

- a fixed adjacent lifecycle state machine;
- complete policy validation with non-configurable safety invariants;
- proposal and approval separation;
- stage-bound evidence and work assignment records;
- canonical JSON hashing;
- exclusive event-file creation;
- atomic snapshot replacement; and
- deterministic dependency injection for tests.

Names in code and documentation were selected for direct industry-neutral
meaning. Examples describe a fictional document-intake pilot and contain no
real person, customer, organization, endpoint, or production record.

## Repository scan

`tools/repo_scan.py` contains an isolated machine-readable exception:
task-supplied source-boundary label variants and the personal marker observed
in path metadata are Base64-encoded inside the scanner. At runtime the scanner
decodes, case-folds, and rejects their plaintext appearance anywhere in
ordinary repository content. Encoding prevents the scanner from matching its
own denylist.

Future maintainers who conduct authorized high-level inspection must:

1. avoid opening implementation content unless the governing process permits
   it;
2. record only broad, generic capability categories;
3. add any encountered personal, internal, customer-specific, or
   source-specific labels to the isolated encoded denylist;
4. avoid placing those labels elsewhere in the repository; and
5. rerun the complete provenance scan before contribution.

## Contributor obligations

Contributors must identify the origin and license of any non-original
material. Material without clear reuse rights must not be submitted. A
mechanical rewrite, translation, renamed copy, or behaviorally imitative test
derived from a restricted source is not acceptable.

## Verification

The release checklist requires:

- provenance denylist scan;
- license and third-party notice review;
- contributor origin confirmation;
- credential and personal-data review; and
- confirmation that examples remain synthetic.

This record documents process, not legal advice or a guarantee of
non-infringement.
