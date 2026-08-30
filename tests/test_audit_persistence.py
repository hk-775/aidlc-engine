from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from unittest import mock

from aidlc.audit import canonical_bytes, event_hash, state_digest
from aidlc.errors import ConflictError, IntegrityError, PersistenceError
from aidlc.service import sha256_digest
from tests.support import GovernedProjectTestCase, WorkspaceTestCase


class AuditIntegrityTests(GovernedProjectTestCase):
    def _event_paths(self) -> list[Path]:
        return sorted(self.repository.audit_dir.glob("*.json"))

    @staticmethod
    def _rewrite_json(path: Path, value: dict[str, object]) -> None:
        path.chmod(0o600)
        path.write_bytes(canonical_bytes(value) + b"\n")

    def test_initial_audit_event_is_valid(self) -> None:
        result = self.repository.verify_audit()
        self.assertTrue(result["valid"])
        self.assertEqual(result["event_count"], 1)

    def test_each_mutation_appends_exactly_one_event(self) -> None:
        before = self.repository.verify_audit()["event_count"]
        self.service.register_artifact(
            actor=self.owner,
            artifact_type="opportunity_brief",
            title="Evidence",
            digest=sha256_digest(b"evidence"),
        )
        after = self.repository.verify_audit()["event_count"]
        self.assertEqual(after, before + 1)

    def test_events_are_contiguous_and_hash_linked(self) -> None:
        self.fulfill_current_stage()
        events = self.repository.list_events()
        self.assertEqual(
            [event["sequence"] for event in events],
            list(range(1, len(events) + 1)),
        )
        for previous, current in zip(events, events[1:]):
            self.assertEqual(current["previous_hash"], previous["hash"])

    def test_final_event_binds_current_state_content(self) -> None:
        self.fulfill_current_stage()
        state = self.repository.load()
        final_event = self.repository.list_events()[-1]
        self.assertEqual(final_event["state_digest"], state_digest(state))

    def test_modified_event_content_is_detected(self) -> None:
        self.fulfill_current_stage()
        event_path = self._event_paths()[-1]
        event = json.loads(event_path.read_text(encoding="utf-8"))
        event["payload"]["assignment_id"] = "work_changed"
        self._rewrite_json(event_path, event)
        with self.assertRaises(IntegrityError):
            self.repository.verify_audit()

    def test_deleted_event_is_detected(self) -> None:
        self.fulfill_current_stage()
        self._event_paths()[-1].unlink()
        with self.assertRaises(IntegrityError):
            self.repository.verify_audit()

    def test_unexpected_audit_file_is_detected(self) -> None:
        (self.repository.audit_dir / "notes.txt").write_text(
            "unexpected",
            encoding="utf-8",
        )
        with self.assertRaises(IntegrityError):
            self.repository.verify_audit()

    def test_event_filename_mismatch_is_detected(self) -> None:
        event_path = self._event_paths()[0]
        renamed = event_path.with_name("00000001-event_mismatch.json")
        event_path.rename(renamed)
        with self.assertRaises(IntegrityError):
            self.repository.verify_audit()

    def test_state_content_tampering_is_detected(self) -> None:
        state = json.loads(self.repository.state_path.read_text(encoding="utf-8"))
        state["current_stage"] = "requirements"
        self.repository.state_path.write_bytes(canonical_bytes(state) + b"\n")
        with self.assertRaises(IntegrityError):
            self.repository.verify_audit()

    def test_state_head_tampering_is_detected(self) -> None:
        state = json.loads(self.repository.state_path.read_text(encoding="utf-8"))
        state["audit"]["head_hash"] = "f" * 64
        self.repository.state_path.write_bytes(canonical_bytes(state) + b"\n")
        with self.assertRaises(IntegrityError):
            self.repository.verify_audit()

    def test_internally_rehashed_revision_mismatch_is_detected(self) -> None:
        event_path = self._event_paths()[0]
        event = json.loads(event_path.read_text(encoding="utf-8"))
        event["state_revision"] = 9
        unsigned = dict(event)
        unsigned.pop("hash")
        event["hash"] = event_hash(unsigned)
        self._rewrite_json(event_path, event)
        state = json.loads(self.repository.state_path.read_text(encoding="utf-8"))
        state["audit"]["head_hash"] = event["hash"]
        self.repository.state_path.write_bytes(canonical_bytes(state) + b"\n")
        with self.assertRaises(IntegrityError):
            self.repository.verify_audit()

    def test_policy_tampering_is_detected_on_load(self) -> None:
        policy = json.loads(self.repository.policy_path.read_text(encoding="utf-8"))
        policy["limits"]["max_artifacts"] = 99
        self.repository.policy_path.write_bytes(canonical_bytes(policy) + b"\n")
        with self.assertRaises(IntegrityError):
            self.repository.load()

    def test_event_files_are_written_read_only(self) -> None:
        mode = stat.S_IMODE(self._event_paths()[0].stat().st_mode)
        self.assertEqual(mode & stat.S_IWUSR, 0)

    def test_revision_is_one_less_than_event_count(self) -> None:
        self.fulfill_current_stage()
        state = self.repository.load()
        self.assertEqual(state["revision"], state["audit"]["event_count"] - 1)


class PersistenceRecoveryTests(GovernedProjectTestCase):
    def test_pending_transaction_recovers_after_append_failure(self) -> None:
        original_append = self.repository._append_event
        with mock.patch.object(
            self.repository,
            "_append_event",
            side_effect=PersistenceError("simulated interruption"),
        ):
            with self.assertRaises(PersistenceError):
                self.service.record_risk_acceptance(
                    actor=self.risk_owner,
                    title="Recoverable synthetic risk",
                    rationale="Exercise pending transaction recovery.",
                )
        self.assertTrue(self.repository.pending_path.exists())
        self.repository._append_event = original_append
        state = self.repository.load()
        self.assertFalse(self.repository.pending_path.exists())
        self.assertEqual(len(state["risk_decisions"]), 1)
        self.assertTrue(self.repository.verify_audit()["valid"])

    def test_pending_marker_after_commit_is_cleaned_idempotently(self) -> None:
        self.service.record_risk_acceptance(
            actor=self.risk_owner,
            title="Committed risk",
            rationale="Create a complete transaction.",
        )
        state = self.repository.load()
        event = self.repository.list_events()[-1]
        self.repository._atomic_write_json(
            self.repository.pending_path,
            {"event": event, "state": state},
        )
        reloaded = self.repository.load()
        self.assertEqual(reloaded, state)
        self.assertFalse(self.repository.pending_path.exists())

    def test_invalid_pending_shape_fails_closed(self) -> None:
        self.repository._atomic_write_json(
            self.repository.pending_path,
            {"unexpected": {}},
        )
        with self.assertRaises(IntegrityError):
            self.repository.load()
        self.assertTrue(self.repository.pending_path.exists())

    def test_failed_domain_mutation_leaves_state_unchanged(self) -> None:
        before = self.repository.load()
        with self.assertRaises(ConflictError):
            self.service.propose_transition(
                actor=self.agent,
                rationale="Missing evidence.",
                evidence_ids=[],
            )
        after = self.repository.load()
        self.assertEqual(after, before)

    def test_atomic_write_leaves_no_temporary_files(self) -> None:
        self.service.register_artifact(
            actor=self.owner,
            artifact_type="opportunity_brief",
            title="Evidence",
            digest=sha256_digest(b"temporary-file-check"),
        )
        temporary_names = [
            path.name
            for path in self.repository.root.iterdir()
            if path.name.endswith(".tmp")
        ]
        self.assertEqual(temporary_names, [])

    def test_initialization_is_not_repeatable_in_same_store(self) -> None:
        with self.assertRaises(ConflictError):
            self.service.initialize(
                name="Duplicate",
                description="Must fail",
                creator=self.owner,
            )


class StorageBoundaryTests(WorkspaceTestCase):
    def test_symbolic_link_project_root_is_rejected(self) -> None:
        real = self.workspace / "real"
        real.mkdir()
        linked = self.workspace / "linked"
        os.symlink(real, linked)
        from aidlc.persistence import JsonProjectRepository

        repository = JsonProjectRepository(linked)
        with self.assertRaises(PersistenceError) as context:
            repository.load()
        self.assertEqual(context.exception.code, "unsafe_storage_path")
