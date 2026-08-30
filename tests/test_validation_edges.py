from __future__ import annotations

import copy
import json
from datetime import datetime

from aidlc.audit import GENESIS_HASH, validate_event, verify_event
from aidlc.errors import (
    ConflictError,
    IntegrityError,
    NotFoundError,
    PersistenceError,
    ValidationError,
)
from aidlc.models import Actor, validate_state, validate_text
from aidlc.persistence import JsonProjectRepository
from aidlc.policy import default_policy, validate_policy
from aidlc.service import sha256_digest
from aidlc.values import (
    DeterministicValueProvider,
    format_timestamp,
    parse_timestamp,
)
from tests.support import GovernedProjectTestCase, WorkspaceTestCase


class AuditValidationEdgeTests(GovernedProjectTestCase):
    def test_each_audit_field_rejects_malformed_content(self) -> None:
        valid = self.repository.list_events()[0]
        cases = {
            "schema_version": ("schema_version", 2),
            "sequence": ("sequence", 0),
            "event_id": ("event_id", "Bad Event"),
            "timestamp": ("timestamp", "not-a-time"),
            "type": ("type", ""),
            "actor": ("actor", []),
            "project_id": ("project_id", "Bad Project"),
            "state_revision": ("state_revision", -1),
            "state_digest": ("state_digest", "short"),
            "payload": ("payload", []),
            "previous_hash": ("previous_hash", "short"),
            "hash": ("hash", "short"),
        }
        for name, (field, value) in cases.items():
            with self.subTest(name=name):
                event = copy.deepcopy(valid)
                event[field] = value
                with self.assertRaises(ValidationError):
                    validate_event(event)
        with self.assertRaises(ValidationError):
            validate_event([])  # type: ignore[arg-type]

    def test_actor_shape_in_event_is_exact(self) -> None:
        event = copy.deepcopy(self.repository.list_events()[0])
        event["actor"]["extra"] = True
        with self.assertRaises(ValidationError):
            validate_event(event)

    def test_wrong_previous_hash_is_detected(self) -> None:
        event = self.repository.list_events()[0]
        with self.assertRaises(IntegrityError):
            verify_event(event, "f" * 64)


class ModelValidationEdgeTests(GovernedProjectTestCase):
    def test_text_validation_rejects_type_length_and_control_character(self) -> None:
        with self.assertRaises(ValidationError):
            validate_text(5, "value")  # type: ignore[arg-type]
        with self.assertRaises(ValidationError):
            validate_text("", "value")
        with self.assertRaises(ValidationError):
            validate_text("bad\x00value", "value")

    def test_state_scalar_fields_are_validated(self) -> None:
        base = self.repository.load()
        mutations = (
            lambda state: state.update(schema_version=2),
            lambda state: state.update(revision=-1),
            lambda state: state.update(policy_digest="short"),
            lambda state: state.update(project=[]),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                state = copy.deepcopy(base)
                mutate(state)
                with self.assertRaises(ValidationError):
                    validate_state(state)
        with self.assertRaises(ValidationError):
            validate_state([])  # type: ignore[arg-type]

    def test_state_project_and_collection_fields_are_validated(self) -> None:
        base = self.repository.load()
        state = copy.deepcopy(base)
        state["project"]["created_at"] = "bad"
        with self.assertRaises(ValidationError):
            validate_state(state)
        for collection in (
            "artifacts",
            "assignments",
            "transition_proposals",
            "risk_decisions",
        ):
            with self.subTest(collection=collection):
                state = copy.deepcopy(base)
                state[collection] = []
                with self.assertRaises(ValidationError):
                    validate_state(state)
        state = copy.deepcopy(base)
        state["artifacts"]["artifact_bad"] = {"id": "artifact_other"}
        with self.assertRaises(ValidationError):
            validate_state(state)

    def test_state_audit_fields_are_validated(self) -> None:
        base = self.repository.load()
        for audit in (
            [],
            {"event_count": 0, "head_hash": "0" * 64},
            {"event_count": 1, "head_hash": "short"},
        ):
            with self.subTest(audit=audit):
                state = copy.deepcopy(base)
                state["audit"] = audit
                with self.assertRaises(ValidationError):
                    validate_state(state)


class PolicyValidationEdgeTests(WorkspaceTestCase):
    def test_policy_container_types_fail_closed(self) -> None:
        with self.assertRaises(ValidationError):
            validate_policy([])  # type: ignore[arg-type]
        fields = (
            "required_artifacts",
            "human_gates",
            "agent_permissions",
            "transition_controls",
            "artifact_controls",
            "limits",
        )
        for field in fields:
            with self.subTest(field=field):
                policy = default_policy()
                policy[field] = []
                with self.assertRaises(ValidationError):
                    validate_policy(policy)

    def test_policy_version_and_nested_types_are_validated(self) -> None:
        policy = default_policy()
        policy["schema_version"] = 2
        with self.assertRaises(ValidationError):
            validate_policy(policy)

        policy = default_policy()
        policy["required_artifacts"]["discovery"] = "brief"
        with self.assertRaises(ValidationError):
            validate_policy(policy)

        policy = default_policy()
        policy["human_gates"]["design->implementation"] = []
        with self.assertRaises(ValidationError):
            validate_policy(policy)

        policy = default_policy()
        policy["human_gates"]["design->implementation"]["required_roles"] = []
        with self.assertRaises(ValidationError):
            validate_policy(policy)

    def test_policy_boolean_fields_require_booleans(self) -> None:
        policy = default_policy()
        policy["agent_permissions"]["propose_work"] = "yes"
        with self.assertRaises(ValidationError):
            validate_policy(policy)

        policy = default_policy()
        policy["transition_controls"]["block_with_open_assignments"] = "yes"
        with self.assertRaises(ValidationError):
            validate_policy(policy)

        policy = default_policy()
        policy["artifact_controls"]["agent_submission_requires_active_assignment"] = "yes"
        with self.assertRaises(ValidationError):
            validate_policy(policy)

    def test_policy_limits_enforce_range(self) -> None:
        for field, value in (
            ("max_artifacts", 0),
            ("max_open_assignments", 10001),
            ("max_pending_proposals", 1001),
        ):
            with self.subTest(field=field):
                policy = default_policy()
                policy["limits"][field] = value
                with self.assertRaises(ValidationError):
                    validate_policy(policy)


class ValueValidationEdgeTests(WorkspaceTestCase):
    def test_timestamp_helpers_reject_invalid_values(self) -> None:
        with self.assertRaises(ValidationError):
            format_timestamp(datetime(2026, 1, 1))
        with self.assertRaises(ValidationError):
            parse_timestamp("not-a-time")
        with self.assertRaises(ValidationError):
            parse_timestamp("2026-01-01T10:00:00")

    def test_deterministic_provider_rejects_empty_seed_and_naive_time(self) -> None:
        with self.assertRaises(ValidationError):
            DeterministicValueProvider("", parse_timestamp("2026-01-01T00:00:00Z"))
        with self.assertRaises(ValidationError):
            DeterministicValueProvider("seed", datetime(2026, 1, 1))


class ServiceValidationEdgeTests(GovernedProjectTestCase):
    def test_artifact_input_shapes_are_validated(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.register_artifact(
                actor=self.owner,
                artifact_type="Bad Type",
                title="Bad type",
                digest=sha256_digest(b"bad"),
            )
        with self.assertRaises(ValidationError):
            self.service.register_artifact(
                actor=self.owner,
                artifact_type="opportunity_brief",
                title="Bad digest",
                digest="short",
            )
        with self.assertRaises(ValidationError):
            self.service.register_artifact(
                actor=self.owner,
                artifact_type="opportunity_brief",
                title="Bad locator",
                digest=sha256_digest(b"locator"),
                locator=5,  # type: ignore[arg-type]
            )
        with self.assertRaises(ValidationError):
            self.service.register_artifact(
                actor=self.owner,
                artifact_type="opportunity_brief",
                title="Bad slash",
                digest=sha256_digest(b"slash"),
                locator="evidence\\brief.md",
            )

    def test_work_deliverables_require_nonempty_unique_types(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.propose_work(
                actor=self.owner,
                assignee_id="Bad Assignee",
                stage="discovery",
                summary="Invalid assignee",
                deliverable_types=["opportunity_brief"],
            )
        with self.assertRaises(ValidationError):
            self.service.propose_work(
                actor=self.agent,
                assignee_id=self.agent.actor_id,
                stage="discovery",
                summary="No deliverables",
                deliverable_types=[],
            )
        with self.assertRaises(ValidationError):
            self.service.propose_work(
                actor=self.agent,
                assignee_id=self.agent.actor_id,
                stage="discovery",
                summary="Duplicate deliverables",
                deliverable_types=["opportunity_brief", "opportunity_brief"],
            )

    def test_missing_assignment_operations_report_not_found(self) -> None:
        with self.assertRaises(NotFoundError):
            self.service.approve_work(actor=self.owner, assignment_id="work_missing")
        with self.assertRaises(NotFoundError):
            self.service.complete_work(actor=self.agent, assignment_id="work_missing")
        with self.assertRaises(NotFoundError):
            self.service.register_artifact(
                actor=self.owner,
                artifact_type="opportunity_brief",
                title="Unknown assignment",
                digest=sha256_digest(b"unknown"),
                assignment_id="work_missing",
            )

    def test_transition_identifier_and_status_errors(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.propose_transition(
                actor=self.agent,
                rationale="Duplicate evidence ids.",
                evidence_ids=["artifact_one", "artifact_one"],
            )
        with self.assertRaises(NotFoundError):
            self.service.approve_transition(
                actor=self.owner,
                proposal_id="proposal_missing",
            )
        with self.assertRaises(NotFoundError):
            self.service.reject_transition(
                actor=self.owner,
                proposal_id="proposal_missing",
                reason="Missing proposal.",
            )

    def test_approved_assignment_cannot_be_approved_again(self) -> None:
        assignment = self.service.propose_work(
            actor=self.agent,
            assignee_id=self.agent.actor_id,
            stage="discovery",
            summary="Single approval",
            deliverable_types=["opportunity_brief"],
        )["assignment"]
        self.service.approve_work(actor=self.owner, assignment_id=assignment["id"])
        with self.assertRaises(ConflictError):
            self.service.approve_work(actor=self.reviewer, assignment_id=assignment["id"])

    def test_gate_requires_explicit_role_name(self) -> None:
        self.advance_to("design")
        proposal = self.propose_current_transition()
        with self.assertRaises(Exception) as context:
            self.service.approve_transition(
                actor=self.reviewer,
                proposal_id=proposal["id"],
            )
        self.assertEqual(getattr(context.exception, "code", None), "gate_role_required")

    def test_collection_limits_are_enforced(self) -> None:
        policy = default_policy()
        policy["limits"]["max_artifacts"] = 1
        policy["limits"]["max_open_assignments"] = 1
        repository, service = self.create_project(
            path=self.workspace / "limited",
            policy=policy,
        )
        service.register_artifact(
            actor=self.owner,
            artifact_type="opportunity_brief",
            title="First",
            digest=sha256_digest(b"first"),
        )
        with self.assertRaises(ConflictError):
            service.register_artifact(
                actor=self.owner,
                artifact_type="supporting_note",
                title="Second",
                digest=sha256_digest(b"second"),
            )
        service.propose_work(
            actor=self.agent,
            assignee_id=self.agent.actor_id,
            stage="discovery",
            summary="First work",
            deliverable_types=["opportunity_brief"],
        )
        with self.assertRaises(ConflictError):
            service.propose_work(
                actor=self.other_agent,
                assignee_id=self.other_agent.actor_id,
                stage="discovery",
                summary="Second work",
                deliverable_types=["opportunity_brief"],
            )
        self.assertEqual(repository.load()["audit"]["event_count"], 3)


class PersistenceValidationEdgeTests(WorkspaceTestCase):
    def test_non_directory_root_is_rejected(self) -> None:
        path = self.workspace / "file-root"
        path.write_text("not a directory\n", encoding="utf-8")
        repository = JsonProjectRepository(path)
        with self.assertRaises(PersistenceError):
            repository.load()

    def test_missing_audit_directory_is_reported(self) -> None:
        path = self.workspace / "incomplete"
        path.mkdir()
        repository = JsonProjectRepository(path)
        with self.assertRaises(NotFoundError):
            repository.load()

    def test_malformed_and_nonobject_json_are_rejected(self) -> None:
        repository, _ = self.create_project(path=self.workspace / "malformed")
        repository.state_path.write_text("{bad\n", encoding="utf-8")
        with self.assertRaises(PersistenceError):
            repository.load()

        repository, _ = self.create_project(path=self.workspace / "array")
        repository.state_path.write_text("[]\n", encoding="utf-8")
        with self.assertRaises(PersistenceError):
            repository.load()

    def test_mutation_callback_must_return_mutation_result(self) -> None:
        repository, _ = self.create_project(path=self.workspace / "mutation")
        with self.assertRaises(PersistenceError):
            repository.mutate(
                Actor("human_owner", "human"),
                lambda state, policy, values: {},  # type: ignore[arg-type,return-value]
            )

    def test_policy_only_partial_initialization_can_restart(self) -> None:
        path = self.workspace / "partial-init"
        repository = JsonProjectRepository(path)
        repository._prepare_root(create=True)
        repository._atomic_write_json(repository.policy_path, default_policy())
        from aidlc.service import LifecycleService

        state = LifecycleService(repository).initialize(
            name="Recovered initialization",
            description="Policy existed without state or events.",
            creator=Actor("human_owner", "human"),
        )
        self.assertEqual(state["current_stage"], "discovery")
