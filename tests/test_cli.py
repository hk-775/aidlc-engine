from __future__ import annotations

import io
import json
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from aidlc_engine.cli import build_parser, main
from tests.support import ROOT, WorkspaceTestCase


class CLITests(WorkspaceTestCase):
    def run_cli(self, *arguments: str) -> tuple[int, dict[str, object], str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(list(arguments))
        output = stdout.getvalue() if code == 0 else stderr.getvalue()
        return code, json.loads(output), stdout.getvalue()

    def deterministic_options(self) -> tuple[str, ...]:
        return (
            "--id-seed",
            "cli-test",
            "--fixed-time",
            "2026-02-02T10:00:00Z",
        )

    def test_default_store_uses_engine_slug(self) -> None:
        args = build_parser().parse_args(["status"])
        self.assertEqual(build_parser().prog, "aidlc-engine")
        self.assertEqual(args.store, ".aidlc-engine")

    def test_explicit_legacy_store_path_remains_supported(self) -> None:
        store = self.workspace / ".aidlc"
        code, demo, _ = self.run_cli("--store", str(store), "demo")
        self.assertEqual(code, 0)
        self.assertEqual(demo["demo"]["current_stage"], "release")
        code, status, _ = self.run_cli("--store", str(store), "status")
        self.assertEqual(code, 0)
        self.assertEqual(status["state"]["current_stage"], "release")

    def test_init_emits_machine_readable_state(self) -> None:
        store = self.workspace / "cli-project"
        code, output, _ = self.run_cli(
            "--store",
            str(store),
            *self.deterministic_options(),
            "init",
            "--name",
            "CLI project",
            "--description",
            "Synthetic",
            "--actor-id",
            "human_owner",
            "--actor-kind",
            "human",
            "--role",
            "project_owner",
        )
        self.assertEqual(code, 0)
        self.assertTrue(output["ok"])
        self.assertEqual(output["state"]["current_stage"], "discovery")

    def test_status_missing_store_returns_not_found_json(self) -> None:
        store = self.workspace / "missing"
        code, output, _ = self.run_cli("--store", str(store), "status")
        self.assertEqual(code, 5)
        self.assertFalse(output["ok"])
        self.assertEqual(output["error"]["code"], "not_found")
        self.assertFalse(store.exists())

    def test_deterministic_options_must_be_paired(self) -> None:
        code, output, _ = self.run_cli(
            "--store",
            str(self.workspace / "project"),
            "--id-seed",
            "only-seed",
            "status",
        )
        self.assertEqual(code, 2)
        self.assertEqual(output["error"]["code"], "validation_error")

    def test_validate_policy_command(self) -> None:
        code, output, _ = self.run_cli(
            "validate-policy",
            "--file",
            str(ROOT / "examples" / "policy.strict.json"),
        )
        self.assertEqual(code, 0)
        self.assertTrue(output["valid"])

    def test_demo_command_runs_full_workflow(self) -> None:
        code, output, _ = self.run_cli(
            "--store",
            str(self.workspace / "demo"),
            "demo",
        )
        self.assertEqual(code, 0)
        self.assertEqual(output["demo"]["current_stage"], "release")
        self.assertEqual(output["demo"]["event_count"], 32)

    def test_forbidden_agent_operation_returns_nonzero_json(self) -> None:
        store = self.workspace / "demo"
        self.run_cli("--store", str(store), "demo")
        code, output, _ = self.run_cli(
            "--store",
            str(store),
            "guard-operation",
            "--actor-id",
            "agent_builder",
            "--actor-kind",
            "agent",
            "--operation",
            "release",
        )
        self.assertEqual(code, 3)
        self.assertEqual(output["error"]["code"], "forbidden_operation")

    def test_pretty_output_is_valid_indented_json(self) -> None:
        store = self.workspace / "pretty"
        code, output, raw_stdout = self.run_cli(
            "--store",
            str(store),
            "--pretty",
            *self.deterministic_options(),
            "init",
            "--name",
            "Pretty project",
            "--actor-id",
            "human_owner",
            "--actor-kind",
            "human",
        )
        self.assertEqual(code, 0)
        self.assertTrue(output["ok"])
        self.assertIn("\n  \"ok\"", raw_stdout)

    def test_events_command_returns_sequence(self) -> None:
        store = self.workspace / "events"
        self.run_cli("--store", str(store), "demo")
        code, output, _ = self.run_cli("--store", str(store), "events")
        self.assertEqual(code, 0)
        self.assertEqual(len(output["events"]), 32)
        self.assertEqual(output["events"][0]["sequence"], 1)

    def test_verify_audit_command(self) -> None:
        store = self.workspace / "verify"
        self.run_cli("--store", str(store), "demo")
        code, output, _ = self.run_cli("--store", str(store), "verify-audit")
        self.assertEqual(code, 0)
        self.assertTrue(output["audit"]["valid"])

    def test_add_artifact_hashes_local_file(self) -> None:
        store = self.workspace / "artifact"
        self.run_cli(
            "--store",
            str(store),
            *self.deterministic_options(),
            "init",
            "--name",
            "Artifact project",
            "--actor-id",
            "human_owner",
            "--actor-kind",
            "human",
        )
        evidence = self.workspace / "evidence.md"
        evidence.write_text("synthetic evidence\n", encoding="utf-8")
        code, output, _ = self.run_cli(
            "--store",
            str(store),
            *self.deterministic_options(),
            "add-artifact",
            "--actor-id",
            "human_owner",
            "--actor-kind",
            "human",
            "--type",
            "opportunity_brief",
            "--title",
            "Local evidence",
            "--file",
            str(evidence),
        )
        self.assertEqual(code, 0)
        self.assertTrue(output["artifact"]["digest"].startswith("sha256:"))
        self.assertEqual(output["artifact"]["locator"], "evidence.md")

    def test_module_entrypoint_runs_in_subprocess(self) -> None:
        environment = {
            **dict(),
            "PYTHONPATH": str(ROOT / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        completed = subprocess.run(
            [sys.executable, "-m", "aidlc_engine", "--help"],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("Human-governed", completed.stdout)

    def test_invalid_actor_is_reported_without_traceback(self) -> None:
        code, output, _ = self.run_cli(
            "--store",
            str(self.workspace / "invalid"),
            "init",
            "--name",
            "Invalid actor",
            "--actor-id",
            "Bad Actor",
            "--actor-kind",
            "human",
        )
        self.assertEqual(code, 2)
        self.assertEqual(output["error"]["code"], "validation_error")

    def test_full_manual_cli_flow_covers_mutating_commands(self) -> None:
        store = self.workspace / "manual-flow"
        global_args = ("--store", str(store), *self.deterministic_options())
        code, _, _ = self.run_cli(
            *global_args,
            "init",
            "--name",
            "Manual flow",
            "--actor-id",
            "human_owner",
            "--actor-kind",
            "human",
            "--role",
            "project_owner",
        )
        self.assertEqual(code, 0)

        _, proposed, _ = self.run_cli(
            *global_args,
            "propose-work",
            "--actor-id",
            "agent_builder",
            "--actor-kind",
            "agent",
            "--assignee-id",
            "agent_builder",
            "--stage",
            "discovery",
            "--summary",
            "Prepare evidence",
            "--deliverable",
            "opportunity_brief",
        )
        assignment_id = proposed["assignment"]["id"]
        code, _, _ = self.run_cli(
            *global_args,
            "approve-work",
            "--actor-id",
            "human_owner",
            "--actor-kind",
            "human",
            "--assignment-id",
            assignment_id,
        )
        self.assertEqual(code, 0)
        digest = "sha256:" + ("a" * 64)
        _, artifact_output, _ = self.run_cli(
            *global_args,
            "add-artifact",
            "--actor-id",
            "agent_builder",
            "--actor-kind",
            "agent",
            "--type",
            "opportunity_brief",
            "--title",
            "Evidence",
            "--digest",
            digest,
            "--assignment-id",
            assignment_id,
        )
        artifact_id = artifact_output["artifact"]["id"]
        code, _, _ = self.run_cli(
            *global_args,
            "complete-work",
            "--actor-id",
            "agent_builder",
            "--actor-kind",
            "agent",
            "--assignment-id",
            assignment_id,
        )
        self.assertEqual(code, 0)
        _, proposal_output, _ = self.run_cli(
            *global_args,
            "propose-transition",
            "--actor-id",
            "agent_builder",
            "--actor-kind",
            "agent",
            "--rationale",
            "Evidence is ready.",
            "--evidence",
            artifact_id,
        )
        proposal_id = proposal_output["proposal"]["id"]
        code, _, _ = self.run_cli(
            *global_args,
            "reject-transition",
            "--actor-id",
            "human_owner",
            "--actor-kind",
            "human",
            "--proposal-id",
            proposal_id,
            "--reason",
            "Clarify the rationale.",
        )
        self.assertEqual(code, 0)
        _, replacement_output, _ = self.run_cli(
            *global_args,
            "propose-transition",
            "--actor-id",
            "agent_builder",
            "--actor-kind",
            "agent",
            "--rationale",
            "Evidence is ready after clarification.",
            "--evidence",
            artifact_id,
        )
        code, approval, _ = self.run_cli(
            *global_args,
            "approve-transition",
            "--actor-id",
            "human_owner",
            "--actor-kind",
            "human",
            "--proposal-id",
            replacement_output["proposal"]["id"],
        )
        self.assertEqual(code, 0)
        self.assertTrue(approval["transition_executed"])
        code, risk, _ = self.run_cli(
            *global_args,
            "accept-risk",
            "--actor-id",
            "human_risk_owner",
            "--actor-kind",
            "human",
            "--role",
            "risk_owner",
            "--title",
            "Synthetic risk",
            "--rationale",
            "Accepted for CLI coverage.",
        )
        self.assertEqual(code, 0)
        self.assertEqual(risk["risk_decision"]["decision"], "accepted")
        code, policy, _ = self.run_cli("--store", str(store), "policy")
        self.assertEqual(code, 0)
        self.assertEqual(policy["policy"]["schema_version"], 1)

    def test_invalid_json_and_missing_artifact_file_are_reported(self) -> None:
        invalid_policy = self.workspace / "invalid-policy.json"
        invalid_policy.write_text("[]\n", encoding="utf-8")
        code, output, _ = self.run_cli(
            "validate-policy",
            "--file",
            str(invalid_policy),
        )
        self.assertEqual(code, 2)
        self.assertEqual(output["error"]["code"], "validation_error")

        store = self.workspace / "missing-file"
        self.run_cli(
            "--store",
            str(store),
            *self.deterministic_options(),
            "init",
            "--name",
            "Missing file",
            "--actor-id",
            "human_owner",
            "--actor-kind",
            "human",
        )
        code, output, _ = self.run_cli(
            "--store",
            str(store),
            "add-artifact",
            "--actor-id",
            "human_owner",
            "--actor-kind",
            "human",
            "--type",
            "opportunity_brief",
            "--title",
            "Missing",
            "--file",
            str(self.workspace / "does-not-exist.md"),
        )
        self.assertEqual(code, 7)
        self.assertEqual(output["error"]["code"], "persistence_error")
