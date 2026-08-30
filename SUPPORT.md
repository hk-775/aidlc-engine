# Support

AIDLC is a community open-source candidate with no paid support, uptime
commitment, response guarantee, or production service.

## Where to ask

- Use the question issue form for reproducible, non-sensitive usage questions
  after a public project tracker is configured.
- Use the bug form for incorrect behavior.
- Use a private channel for security issues as described in `SECURITY.md`.
- Use governance processes for scope, conduct, or maintainer decisions.

Before asking, run:

```console
python3 --version
make test
make scan
PYTHONPATH=src python3 tools/demo_check.py
```

Include the operating system, Python version, command, machine-readable error,
and a minimal synthetic reproduction. Do not attach a real project store if it
contains sensitive evidence or actor information.

## Scope

Community support can reasonably cover:

- local setup on a supported POSIX environment;
- policy validation;
- lifecycle and assignment behavior;
- audit verification;
- repository tests and scans; and
- documentation corrections.

It does not cover:

- production deployment design;
- legal, regulatory, certification, or compliance advice;
- incident response for third-party systems;
- custom delivery-system integrations; or
- recovery guarantees for corrupted or lost local data.
