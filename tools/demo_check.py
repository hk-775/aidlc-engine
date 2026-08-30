#!/usr/bin/env python3
"""Run the full synthetic lifecycle in temporary workspace-local storage."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aidlc_engine.demo import run_demo  # noqa: E402
from aidlc_engine.errors import ForbiddenOperationError  # noqa: E402
from aidlc_engine.models import Actor  # noqa: E402
from aidlc_engine.persistence import JsonProjectRepository  # noqa: E402
from aidlc_engine.service import LifecycleService  # noqa: E402


def main() -> int:
    temporary_root = ROOT / ".tmp"
    temporary_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="demo-check-", dir=temporary_root) as directory:
        result = run_demo(directory)
        service = LifecycleService(JsonProjectRepository(directory))
        denied = False
        try:
            service.guard_operation(actor=Actor("agent_builder", "agent"), operation="release")
        except ForbiddenOperationError:
            denied = True
        checks = {
            "terminal_stage_reached": result["current_stage"] == "release",
            "audit_valid": result["audit_valid"],
            "agent_release_denied": denied,
            "expected_event_count": result["event_count"] == 32,
        }
        output = {
            "ok": all(checks.values()),
            "checks": checks,
            "demo": result,
        }
        print(json.dumps(output, sort_keys=True))
        return 0 if output["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
