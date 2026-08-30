from __future__ import annotations

import copy

from aidlc.errors import AuthorizationError, ForbiddenOperationError
from aidlc.models import HARD_DENIED_AGENT_OPERATIONS, Actor
from aidlc.persistence import JsonProjectRepository
from aidlc.policy import default_policy
from aidlc.service import LifecycleService
from tests.support import GovernedProjectTestCase, WorkspaceTestCase


class AgentRestrictionTests(GovernedProjectTestCase):
    def test_every_hard_denied_operation_fails_for_agent(self) -> None:
        for operation in sorted(HARD_DENIED_AGENT_OPERATIONS):
            with self.subTest(operation=operation):
                with self.assertRaises(ForbiddenOperationError):
                    self.service.guard_operation(actor=self.agent, operation=operation)

    def test_proposal_operations_can_be_guarded_as_allowed(self) -> None:
        for operation in (
            "propose_work",
            "submit_artifact",
            "complete_assigned_work",
            "propose_transition",
        ):
            with self.subTest(operation=operation):
                result = self.service.guard_operation(
                    actor=self.agent,
                    operation=operation,
                )
                self.assertTrue(result["authorized"])

    def test_policy_can_disable_agent_proposal_capability(self) -> None:
        policy = default_policy()
        policy["agent_permissions"]["propose_work"] = False
        path = self.workspace / "disabled"
        repository, service = self.create_project(path=path, policy=policy)
        del repository
        with self.assertRaises(AuthorizationError) as context:
            service.propose_work(
                actor=self.agent,
                assignee_id=self.agent.actor_id,
                stage="discovery",
                summary="Disabled operation",
                deliverable_types=["opportunity_brief"],
            )
        self.assertEqual(context.exception.code, "agent_permission_disabled")

    def test_human_external_execution_is_not_supported(self) -> None:
        for operation in ("merge", "deploy", "release"):
            with self.subTest(operation=operation):
                with self.assertRaises(ForbiddenOperationError) as context:
                    self.service.guard_operation(actor=self.owner, operation=operation)
                self.assertEqual(
                    context.exception.code,
                    "external_execution_not_supported",
                )

    def test_human_cannot_use_generic_gate_bypass(self) -> None:
        for operation in ("bypass_gate", "satisfy_human_gate"):
            with self.subTest(operation=operation):
                with self.assertRaises(ForbiddenOperationError):
                    self.service.guard_operation(actor=self.owner, operation=operation)

    def test_human_risk_guard_requires_role(self) -> None:
        with self.assertRaises(AuthorizationError) as context:
            self.service.guard_operation(actor=self.owner, operation="accept_risk")
        self.assertEqual(context.exception.code, "risk_owner_required")
        allowed = self.service.guard_operation(
            actor=self.risk_owner,
            operation="accept_risk",
        )
        self.assertTrue(allowed["authorized"])

    def test_unknown_operation_fails_closed(self) -> None:
        with self.assertRaises(Exception) as context:
            self.service.guard_operation(actor=self.agent, operation="invent_authority")
        self.assertEqual(getattr(context.exception, "code", None), "validation_error")

    def test_agent_cannot_record_risk_acceptance(self) -> None:
        with self.assertRaises(AuthorizationError) as context:
            self.service.record_risk_acceptance(
                actor=self.agent,
                title="Synthetic risk",
                rationale="Agent must not decide this.",
            )
        self.assertEqual(context.exception.code, "human_actor_required")


class InitializationRestrictionTests(WorkspaceTestCase):
    def test_agent_cannot_initialize_project(self) -> None:
        repository = JsonProjectRepository(self.workspace / "project")
        service = LifecycleService(repository)
        with self.assertRaises(AuthorizationError) as context:
            service.initialize(
                name="Invalid project",
                description="Agent-created",
                creator=Actor("agent_builder", "agent"),
                policy=copy.deepcopy(default_policy()),
            )
        self.assertEqual(context.exception.code, "human_initialization_required")
