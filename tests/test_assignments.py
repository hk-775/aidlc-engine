from __future__ import annotations

from aidlc.errors import AuthorizationError, ConflictError, ValidationError
from aidlc.service import sha256_digest
from tests.support import GovernedProjectTestCase


class AssignmentTests(GovernedProjectTestCase):
    def test_agent_can_propose_work_for_itself(self) -> None:
        assignment = self.service.propose_work(
            actor=self.agent,
            assignee_id=self.agent.actor_id,
            stage="discovery",
            summary="Prepare an opportunity brief",
            deliverable_types=["opportunity_brief"],
        )["assignment"]
        self.assertEqual(assignment["status"], "proposed")
        self.assertEqual(assignment["assignee_id"], self.agent.actor_id)

    def test_agent_cannot_propose_work_for_peer(self) -> None:
        with self.assertRaises(AuthorizationError) as context:
            self.service.propose_work(
                actor=self.agent,
                assignee_id=self.other_agent.actor_id,
                stage="discovery",
                summary="Assign another agent",
                deliverable_types=["opportunity_brief"],
            )
        self.assertEqual(context.exception.code, "agent_cannot_assign_peer")

    def test_work_must_target_current_stage(self) -> None:
        with self.assertRaises(ConflictError):
            self.service.propose_work(
                actor=self.agent,
                assignee_id=self.agent.actor_id,
                stage="requirements",
                summary="Premature requirements work",
                deliverable_types=["delivery_requirements"],
            )

    def test_proposer_cannot_approve_own_work(self) -> None:
        assignment = self.service.propose_work(
            actor=self.owner,
            assignee_id=self.agent.actor_id,
            stage="discovery",
            summary="Human-proposed work",
            deliverable_types=["opportunity_brief"],
        )["assignment"]
        with self.assertRaises(AuthorizationError) as context:
            self.service.approve_work(
                actor=self.owner,
                assignment_id=assignment["id"],
            )
        self.assertEqual(context.exception.code, "self_approval_forbidden")

    def test_human_can_approve_agent_proposal(self) -> None:
        assignment = self.service.propose_work(
            actor=self.agent,
            assignee_id=self.agent.actor_id,
            stage="discovery",
            summary="Prepare an opportunity brief",
            deliverable_types=["opportunity_brief"],
        )["assignment"]
        approved = self.service.approve_work(
            actor=self.owner,
            assignment_id=assignment["id"],
        )["assignment"]
        self.assertEqual(approved["status"], "active")
        self.assertEqual(approved["approved_by"], self.owner.actor_id)

    def test_agent_artifact_requires_active_assignment(self) -> None:
        with self.assertRaises(AuthorizationError) as context:
            self.service.register_artifact(
                actor=self.agent,
                artifact_type="opportunity_brief",
                title="Unassigned brief",
                digest=sha256_digest(b"brief"),
            )
        self.assertEqual(context.exception.code, "active_assignment_required")

    def test_assignment_scope_rejects_wrong_artifact_type(self) -> None:
        assignment = self.service.propose_work(
            actor=self.agent,
            assignee_id=self.agent.actor_id,
            stage="discovery",
            summary="Prepare an opportunity brief",
            deliverable_types=["opportunity_brief"],
        )["assignment"]
        self.service.approve_work(actor=self.owner, assignment_id=assignment["id"])
        with self.assertRaises(AuthorizationError) as context:
            self.service.register_artifact(
                actor=self.agent,
                artifact_type="solution_design",
                title="Wrong scope",
                digest=sha256_digest(b"wrong"),
                assignment_id=assignment["id"],
            )
        self.assertEqual(context.exception.code, "assignment_scope_mismatch")

    def test_other_agent_cannot_use_assignment(self) -> None:
        assignment = self.service.propose_work(
            actor=self.agent,
            assignee_id=self.agent.actor_id,
            stage="discovery",
            summary="Prepare an opportunity brief",
            deliverable_types=["opportunity_brief"],
        )["assignment"]
        self.service.approve_work(actor=self.owner, assignment_id=assignment["id"])
        with self.assertRaises(AuthorizationError):
            self.service.register_artifact(
                actor=self.other_agent,
                artifact_type="opportunity_brief",
                title="Peer submission",
                digest=sha256_digest(b"peer"),
                assignment_id=assignment["id"],
            )

    def test_completion_requires_all_deliverables(self) -> None:
        fulfilled = self.fulfill_current_stage(
            extra_deliverables=["acceptance_examples"],
        )
        with self.assertRaises(ConflictError) as context:
            self.service.complete_work(
                actor=self.agent,
                assignment_id=fulfilled["assignment"]["id"],
            )
        self.assertEqual(context.exception.code, "assignment_deliverables_missing")

    def test_assignee_can_complete_after_deliverables(self) -> None:
        fulfilled = self.fulfill_current_stage()
        state = self.repository.load()
        assignment = state["assignments"][fulfilled["assignment"]["id"]]
        self.assertEqual(assignment["status"], "completed")

    def test_non_assignee_cannot_complete_work(self) -> None:
        assignment = self.service.propose_work(
            actor=self.agent,
            assignee_id=self.agent.actor_id,
            stage="discovery",
            summary="Prepare an opportunity brief",
            deliverable_types=["opportunity_brief"],
        )["assignment"]
        self.service.approve_work(actor=self.owner, assignment_id=assignment["id"])
        with self.assertRaises(AuthorizationError) as context:
            self.service.complete_work(
                actor=self.other_agent,
                assignment_id=assignment["id"],
            )
        self.assertEqual(context.exception.code, "assignment_assignee_required")

    def test_human_can_register_artifact_without_assignment(self) -> None:
        artifact = self.service.register_artifact(
            actor=self.owner,
            artifact_type="opportunity_brief",
            title="Human-authored brief",
            digest=sha256_digest(b"human brief"),
            locator="evidence/brief.md",
        )["artifact"]
        self.assertIsNone(artifact["assignment_id"])

    def test_duplicate_artifact_is_rejected(self) -> None:
        digest = sha256_digest(b"same")
        self.service.register_artifact(
            actor=self.owner,
            artifact_type="opportunity_brief",
            title="First",
            digest=digest,
        )
        with self.assertRaises(ConflictError) as context:
            self.service.register_artifact(
                actor=self.owner,
                artifact_type="opportunity_brief",
                title="Second",
                digest=digest,
            )
        self.assertEqual(context.exception.code, "duplicate_artifact")

    def test_unsafe_artifact_locator_is_rejected(self) -> None:
        for locator in ("../outside.md", "/absolute.md", "https://example.invalid/a"):
            with self.subTest(locator=locator):
                with self.assertRaises(ValidationError):
                    self.service.register_artifact(
                        actor=self.owner,
                        artifact_type="opportunity_brief",
                        title="Unsafe locator",
                        digest=sha256_digest(locator.encode()),
                        locator=locator,
                    )
