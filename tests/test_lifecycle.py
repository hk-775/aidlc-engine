from __future__ import annotations

import copy

from aidlc.errors import AuthorizationError, ConflictError
from aidlc.models import Actor, STAGES
from aidlc.policy import default_policy
from aidlc.service import sha256_digest
from tests.support import GovernedProjectTestCase


class LifecycleTransitionTests(GovernedProjectTestCase):
    def test_project_starts_in_discovery(self) -> None:
        self.assertEqual(self.repository.load()["current_stage"], "discovery")

    def test_ordinary_human_approval_executes_transition(self) -> None:
        proposal = self.propose_current_transition()
        result = self.service.approve_transition(
            actor=self.owner,
            proposal_id=proposal["id"],
        )
        self.assertTrue(result["transition_executed"])
        self.assertEqual(result["current_stage"], "requirements")

    def test_full_lifecycle_reaches_release_in_order(self) -> None:
        observed = [self.repository.load()["current_stage"]]
        while observed[-1] != "release":
            self.advance_once()
            observed.append(self.repository.load()["current_stage"])
        self.assertEqual(observed, list(STAGES))

    def test_missing_evidence_blocks_proposal(self) -> None:
        before = self.repository.load()["audit"]["event_count"]
        with self.assertRaises(ConflictError) as context:
            self.service.propose_transition(
                actor=self.agent,
                rationale="No evidence is available.",
                evidence_ids=[],
            )
        self.assertEqual(context.exception.code, "evidence_requirements_unsatisfied")
        self.assertEqual(self.repository.load()["audit"]["event_count"], before)

    def test_unknown_evidence_identifier_blocks_proposal(self) -> None:
        with self.assertRaises(ConflictError) as context:
            self.service.propose_transition(
                actor=self.agent,
                rationale="Unknown evidence should fail.",
                evidence_ids=["artifact_missing"],
            )
        self.assertEqual(
            context.exception.details["invalid_evidence_ids"],
            ["artifact_missing"],
        )

    def test_evidence_from_prior_stage_is_invalid(self) -> None:
        fulfilled = self.fulfill_current_stage()
        old_artifact_id = fulfilled["artifact"]["id"]
        proposal = self.service.propose_transition(
            actor=self.agent,
            rationale="Discovery evidence is complete.",
            evidence_ids=[old_artifact_id],
        )["proposal"]
        self.service.approve_transition(actor=self.owner, proposal_id=proposal["id"])
        with self.assertRaises(ConflictError) as context:
            self.service.propose_transition(
                actor=self.agent,
                rationale="Old evidence must not satisfy requirements.",
                evidence_ids=[old_artifact_id],
            )
        self.assertIn(
            old_artifact_id,
            context.exception.details["invalid_evidence_ids"],
        )

    def test_only_one_transition_proposal_can_be_pending(self) -> None:
        fulfilled = self.fulfill_current_stage()
        evidence = [fulfilled["artifact"]["id"]]
        self.service.propose_transition(
            actor=self.agent,
            rationale="First proposal.",
            evidence_ids=evidence,
        )
        with self.assertRaises(ConflictError) as context:
            self.service.propose_transition(
                actor=self.agent,
                rationale="Second proposal.",
                evidence_ids=evidence,
            )
        self.assertEqual(context.exception.code, "pending_transition_exists")

    def test_agent_cannot_approve_transition(self) -> None:
        proposal = self.propose_current_transition()
        with self.assertRaises(AuthorizationError) as context:
            self.service.approve_transition(
                actor=self.other_agent,
                proposal_id=proposal["id"],
            )
        self.assertEqual(context.exception.code, "human_actor_required")

    def test_human_proposer_cannot_self_approve(self) -> None:
        fulfilled = self.fulfill_current_stage()
        proposal = self.service.propose_transition(
            actor=self.owner,
            rationale="Human proposal still needs separation.",
            evidence_ids=[fulfilled["artifact"]["id"]],
        )["proposal"]
        with self.assertRaises(AuthorizationError) as context:
            self.service.approve_transition(
                actor=self.owner,
                proposal_id=proposal["id"],
            )
        self.assertEqual(context.exception.code, "self_approval_forbidden")

    def test_design_gate_requires_technical_reviewer_role(self) -> None:
        self.advance_to("design")
        proposal = self.propose_current_transition()
        with self.assertRaises(AuthorizationError) as context:
            self.service.approve_transition(
                actor=self.owner,
                proposal_id=proposal["id"],
                approval_role="technical_reviewer",
            )
        self.assertEqual(context.exception.code, "gate_role_not_held")
        self.assertEqual(self.repository.load()["current_stage"], "design")

    def test_design_gate_executes_with_reviewer(self) -> None:
        self.advance_to("design")
        proposal = self.propose_current_transition()
        result = self.service.approve_transition(
            actor=self.reviewer,
            proposal_id=proposal["id"],
            approval_role="technical_reviewer",
        )
        self.assertTrue(result["transition_executed"])
        self.assertEqual(result["current_stage"], "implementation")

    def test_release_gate_first_approval_does_not_transition(self) -> None:
        self.advance_to("verification")
        proposal = self.propose_current_transition()
        result = self.service.approve_transition(
            actor=self.release_manager,
            proposal_id=proposal["id"],
            approval_role="release_manager",
        )
        self.assertFalse(result["transition_executed"])
        self.assertEqual(self.repository.load()["current_stage"], "verification")

    def test_release_gate_requires_two_distinct_roles(self) -> None:
        self.advance_to("verification")
        proposal = self.propose_current_transition()
        self.service.approve_transition(
            actor=self.release_manager,
            proposal_id=proposal["id"],
            approval_role="release_manager",
        )
        result = self.service.approve_transition(
            actor=self.risk_owner,
            proposal_id=proposal["id"],
            approval_role="risk_owner",
        )
        self.assertTrue(result["transition_executed"])
        self.assertEqual(result["current_stage"], "release")

    def test_gate_can_require_supplemental_approval_after_role_coverage(self) -> None:
        policy = default_policy()
        policy["human_gates"]["design->implementation"]["minimum_approvals"] = 2
        repository, service = self.create_project(
            path=self.workspace / "supplemental-approval",
            policy=policy,
        )
        self.repository = repository
        self.service = service
        self.advance_to("design")
        proposal = self.propose_current_transition()
        first = self.service.approve_transition(
            actor=self.reviewer,
            proposal_id=proposal["id"],
            approval_role="technical_reviewer",
        )
        self.assertFalse(first["transition_executed"])
        second = self.service.approve_transition(
            actor=self.owner,
            proposal_id=proposal["id"],
        )
        self.assertTrue(second["transition_executed"])
        self.assertEqual(second["current_stage"], "implementation")

    def test_same_actor_cannot_approve_twice(self) -> None:
        self.advance_to("verification")
        proposal = self.propose_current_transition()
        self.service.approve_transition(
            actor=self.release_manager,
            proposal_id=proposal["id"],
            approval_role="release_manager",
        )
        with self.assertRaises(ConflictError):
            self.service.approve_transition(
                actor=self.release_manager,
                proposal_id=proposal["id"],
                approval_role="risk_owner",
            )

    def test_required_role_can_only_be_represented_once(self) -> None:
        self.advance_to("verification")
        proposal = self.propose_current_transition()
        self.service.approve_transition(
            actor=self.release_manager,
            proposal_id=proposal["id"],
            approval_role="release_manager",
        )
        second_release_manager = Actor(
            "human_release_backup",
            "human",
            ("release_manager",),
        )
        with self.assertRaises(ConflictError) as context:
            self.service.approve_transition(
                actor=second_release_manager,
                proposal_id=proposal["id"],
                approval_role="release_manager",
            )
        self.assertEqual(context.exception.code, "gate_role_already_approved")

    def test_rejection_keeps_stage_and_allows_reproposal(self) -> None:
        fulfilled = self.fulfill_current_stage()
        proposal = self.service.propose_transition(
            actor=self.agent,
            rationale="Initial proposal.",
            evidence_ids=[fulfilled["artifact"]["id"]],
        )["proposal"]
        rejected = self.service.reject_transition(
            actor=self.owner,
            proposal_id=proposal["id"],
            reason="Review requested clearer rationale.",
        )["proposal"]
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(self.repository.load()["current_stage"], "discovery")
        replacement = self.service.propose_transition(
            actor=self.agent,
            rationale="Updated rationale after human feedback.",
            evidence_ids=[fulfilled["artifact"]["id"]],
        )["proposal"]
        self.assertEqual(replacement["status"], "pending")

    def test_release_is_terminal(self) -> None:
        self.advance_to("release")
        with self.assertRaises(ConflictError):
            self.service.propose_transition(
                actor=self.agent,
                rationale="No stage exists after release.",
                evidence_ids=[],
            )

    def test_open_assignment_blocks_transition(self) -> None:
        artifact = self.service.register_artifact(
            actor=self.owner,
            artifact_type="opportunity_brief",
            title="Ready evidence",
            digest=sha256_digest(b"ready"),
        )["artifact"]
        self.service.propose_work(
            actor=self.agent,
            assignee_id=self.agent.actor_id,
            stage="discovery",
            summary="Still-open follow-up",
            deliverable_types=["opportunity_brief"],
        )
        with self.assertRaises(ConflictError) as context:
            self.service.propose_transition(
                actor=self.agent,
                rationale="Open work should block.",
                evidence_ids=[artifact["id"]],
            )
        self.assertEqual(context.exception.code, "open_assignments_block_transition")

    def test_human_risk_owner_can_record_acceptance(self) -> None:
        result = self.service.record_risk_acceptance(
            actor=self.risk_owner,
            title="Synthetic schedule risk",
            rationale="Accepted for the local demonstration only.",
        )
        self.assertEqual(result["risk_decision"]["decision"], "accepted")

    def test_non_risk_owner_cannot_record_acceptance(self) -> None:
        with self.assertRaises(AuthorizationError) as context:
            self.service.record_risk_acceptance(
                actor=self.owner,
                title="Synthetic schedule risk",
                rationale="Role should be required.",
            )
        self.assertEqual(context.exception.code, "risk_owner_required")


class ConfiguredLifecycleTests(GovernedProjectTestCase):
    def test_policy_can_add_gate_to_other_transition(self) -> None:
        policy = default_policy()
        policy["human_gates"]["discovery->requirements"] = {
            "required_roles": ["project_owner"],
            "minimum_approvals": 1,
        }
        repository, service = self.create_project(
            path=self.workspace / "extra-gate",
            policy=policy,
        )
        self.repository = repository
        self.service = service
        proposal = self.propose_current_transition()
        result = self.service.approve_transition(
            actor=self.owner,
            proposal_id=proposal["id"],
            approval_role="project_owner",
        )
        self.assertTrue(result["transition_executed"])

    def test_multiple_required_artifacts_are_enforced(self) -> None:
        policy = default_policy()
        policy["required_artifacts"]["discovery"].append("acceptance_examples")
        repository, service = self.create_project(
            path=self.workspace / "multi-evidence",
            policy=copy.deepcopy(policy),
        )
        self.repository = repository
        self.service = service
        first = self.service.register_artifact(
            actor=self.owner,
            artifact_type="opportunity_brief",
            title="Opportunity",
            digest=sha256_digest(b"one"),
        )["artifact"]
        with self.assertRaises(ConflictError) as context:
            self.service.propose_transition(
                actor=self.agent,
                rationale="Only one required artifact is present.",
                evidence_ids=[first["id"]],
            )
        self.assertEqual(
            context.exception.details["missing_artifact_types"],
            ["acceptance_examples"],
        )

    def test_open_assignment_control_can_be_disabled(self) -> None:
        policy = default_policy()
        policy["transition_controls"]["block_with_open_assignments"] = False
        repository, service = self.create_project(
            path=self.workspace / "open-work-allowed",
            policy=policy,
        )
        self.repository = repository
        self.service = service
        artifact = service.register_artifact(
            actor=self.owner,
            artifact_type="opportunity_brief",
            title="Evidence",
            digest=sha256_digest(b"evidence"),
        )["artifact"]
        service.propose_work(
            actor=self.agent,
            assignee_id=self.agent.actor_id,
            stage="discovery",
            summary="Open but non-blocking experiment",
            deliverable_types=["opportunity_brief"],
        )
        proposal = service.propose_transition(
            actor=self.agent,
            rationale="Policy allows open work for this experiment.",
            evidence_ids=[artifact["id"]],
        )["proposal"]
        self.assertEqual(proposal["status"], "pending")
