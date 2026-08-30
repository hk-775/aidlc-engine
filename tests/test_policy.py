from __future__ import annotations

import copy
import unittest

from aidlc.errors import ValidationError
from aidlc.models import Actor, STAGES, next_stage, validate_stage
from aidlc.policy import default_policy, validate_policy


class PolicyValidationTests(unittest.TestCase):
    def test_default_policy_is_valid(self) -> None:
        self.assertEqual(validate_policy(default_policy()), default_policy())

    def test_unknown_top_level_field_is_rejected(self) -> None:
        policy = default_policy()
        policy["unexpected"] = True
        with self.assertRaises(ValidationError):
            validate_policy(policy)

    def test_missing_mandatory_gate_is_rejected(self) -> None:
        policy = default_policy()
        del policy["human_gates"]["design->implementation"]
        with self.assertRaisesRegex(ValidationError, "mandatory"):
            validate_policy(policy)

    def test_mandatory_design_role_cannot_be_removed(self) -> None:
        policy = default_policy()
        policy["human_gates"]["design->implementation"]["required_roles"] = [
            "project_owner"
        ]
        with self.assertRaises(ValidationError) as context:
            validate_policy(policy)
        self.assertEqual(context.exception.code, "mandatory_gate_weakened")

    def test_release_gate_minimum_cannot_be_reduced(self) -> None:
        policy = default_policy()
        policy["human_gates"]["verification->release"]["minimum_approvals"] = 1
        with self.assertRaises(ValidationError):
            validate_policy(policy)

    def test_hard_denied_agent_permissions_cannot_be_enabled(self) -> None:
        denied = (
            "merge",
            "deploy",
            "release",
            "accept_risk",
            "approve_transition",
            "satisfy_human_gate",
            "bypass_gate",
        )
        for operation in denied:
            with self.subTest(operation=operation):
                policy = default_policy()
                policy["agent_permissions"][operation] = True
                with self.assertRaises(ValidationError) as context:
                    validate_policy(policy)
                self.assertEqual(context.exception.code, "unsafe_agent_permission")

    def test_independent_approval_cannot_be_disabled(self) -> None:
        policy = default_policy()
        policy["transition_controls"]["require_independent_approval"] = False
        with self.assertRaises(ValidationError) as context:
            validate_policy(policy)
        self.assertEqual(context.exception.code, "unsafe_transition_control")

    def test_human_transition_approval_cannot_be_disabled(self) -> None:
        policy = default_policy()
        policy["transition_controls"][
            "require_human_approval_for_all_transitions"
        ] = False
        with self.assertRaises(ValidationError):
            validate_policy(policy)

    def test_non_adjacent_gate_is_rejected(self) -> None:
        policy = default_policy()
        policy["human_gates"]["discovery->design"] = {
            "required_roles": ["project_owner"],
            "minimum_approvals": 1,
        }
        with self.assertRaises(ValidationError):
            validate_policy(policy)

    def test_duplicate_artifact_requirement_is_rejected(self) -> None:
        policy = default_policy()
        policy["required_artifacts"]["discovery"] = [
            "opportunity_brief",
            "opportunity_brief",
        ]
        with self.assertRaises(ValidationError):
            validate_policy(policy)

    def test_invalid_artifact_type_is_rejected(self) -> None:
        policy = default_policy()
        policy["required_artifacts"]["discovery"] = ["Not Portable"]
        with self.assertRaises(ValidationError):
            validate_policy(policy)

    def test_minimum_approvals_covers_every_role(self) -> None:
        policy = default_policy()
        policy["human_gates"]["requirements->design"] = {
            "required_roles": ["project_owner", "technical_reviewer"],
            "minimum_approvals": 1,
        }
        with self.assertRaises(ValidationError):
            validate_policy(policy)

    def test_boolean_limit_is_rejected(self) -> None:
        policy = default_policy()
        policy["limits"]["max_artifacts"] = True
        with self.assertRaises(ValidationError):
            validate_policy(policy)

    def test_only_sha256_is_supported(self) -> None:
        policy = default_policy()
        policy["artifact_controls"]["digest_algorithm"] = "sha1"
        with self.assertRaises(ValidationError):
            validate_policy(policy)

    def test_validation_returns_a_copy(self) -> None:
        policy = default_policy()
        validated = validate_policy(policy)
        validated["limits"]["max_artifacts"] = 10
        self.assertEqual(policy["limits"]["max_artifacts"], 1000)


class ModelValidationTests(unittest.TestCase):
    def test_agent_cannot_claim_governance_role(self) -> None:
        with self.assertRaises(ValidationError) as context:
            Actor("agent_builder", "agent", ("risk_owner",))
        self.assertEqual(context.exception.code, "agent_governance_role_forbidden")

    def test_actor_roles_are_unique_and_sorted(self) -> None:
        actor = Actor("human_reviewer", "human", ("z_role", "a_role", "z_role"))
        self.assertEqual(actor.roles, ("a_role", "z_role"))

    def test_invalid_actor_kind_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            Actor("human_owner", "service")

    def test_stage_order_is_stable(self) -> None:
        self.assertEqual(next_stage("discovery"), "requirements")
        self.assertEqual(next_stage("release"), None)
        self.assertEqual(len(STAGES), 6)

    def test_unknown_stage_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_stage("planning")
