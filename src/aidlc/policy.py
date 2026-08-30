"""Policy defaults and fail-closed validation."""

from __future__ import annotations

import copy
from typing import Any

from aidlc.errors import ValidationError
from aidlc.models import (
    ADJACENT_TRANSITIONS,
    AGENT_PERMISSION_KEYS,
    ARTIFACT_TYPE_PATTERN,
    HARD_DENIED_AGENT_OPERATIONS,
    HIGH_IMPACT_TRANSITIONS,
    ROLE_PATTERN,
    STAGES,
    require_exact_keys,
    transition_key,
)

MANDATORY_GATE_CONTROLS = {
    transition_key("design", "implementation"): {
        "required_roles": {"technical_reviewer"},
        "minimum_approvals": 1,
    },
    transition_key("verification", "release"): {
        "required_roles": {"release_manager", "risk_owner"},
        "minimum_approvals": 2,
    },
}


def default_policy() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "required_artifacts": {
            "discovery": ["opportunity_brief"],
            "requirements": ["delivery_requirements"],
            "design": ["solution_design"],
            "implementation": ["implementation_record"],
            "verification": ["verification_report"],
            "release": [],
        },
        "human_gates": {
            "design->implementation": {
                "required_roles": ["technical_reviewer"],
                "minimum_approvals": 1,
            },
            "verification->release": {
                "required_roles": ["release_manager", "risk_owner"],
                "minimum_approvals": 2,
            },
        },
        "agent_permissions": {
            "propose_work": True,
            "submit_artifact": True,
            "complete_assigned_work": True,
            "propose_transition": True,
            "merge": False,
            "deploy": False,
            "release": False,
            "accept_risk": False,
            "approve_transition": False,
            "satisfy_human_gate": False,
            "bypass_gate": False,
        },
        "transition_controls": {
            "require_independent_approval": True,
            "require_human_approval_for_all_transitions": True,
            "block_with_open_assignments": True,
        },
        "artifact_controls": {
            "digest_algorithm": "sha256",
            "agent_submission_requires_active_assignment": True,
        },
        "limits": {
            "max_artifacts": 1000,
            "max_open_assignments": 100,
            "max_pending_proposals": 20,
        },
    }


def _validate_string_list(
    value: Any,
    label: str,
    *,
    pattern: Any,
    allow_empty: bool,
) -> list[str]:
    if not isinstance(value, list):
        raise ValidationError(f"{label} must be an array")
    if not allow_empty and not value:
        raise ValidationError(f"{label} cannot be empty")
    if any(not isinstance(item, str) or not pattern.fullmatch(item) for item in value):
        raise ValidationError(
            f"{label} contains an invalid value",
            details={"field": label},
        )
    if len(value) != len(set(value)):
        raise ValidationError(f"{label} cannot contain duplicates")
    return value


def _validate_limit(value: Any, label: str, minimum: int, maximum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValidationError(
            f"{label} must be an integer between {minimum} and {maximum}",
            details={"field": label, "value": value},
        )


def validate_policy(policy: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(policy, dict):
        raise ValidationError("policy must be a JSON object")
    require_exact_keys(
        policy,
        {
            "schema_version",
            "required_artifacts",
            "human_gates",
            "agent_permissions",
            "transition_controls",
            "artifact_controls",
            "limits",
        },
        "policy",
    )
    if policy["schema_version"] != 1:
        raise ValidationError("unsupported policy schema version")

    required = policy["required_artifacts"]
    if not isinstance(required, dict):
        raise ValidationError("required_artifacts must be an object")
    require_exact_keys(required, STAGES, "required_artifacts")
    for stage, artifact_types in required.items():
        _validate_string_list(
            artifact_types,
            f"required_artifacts.{stage}",
            pattern=ARTIFACT_TYPE_PATTERN,
            allow_empty=True,
        )

    gates = policy["human_gates"]
    if not isinstance(gates, dict):
        raise ValidationError("human_gates must be an object")
    adjacent_keys = {transition_key(source, target) for source, target in ADJACENT_TRANSITIONS}
    invalid_keys = set(gates) - adjacent_keys
    if invalid_keys:
        raise ValidationError(
            "human_gates contains a non-adjacent transition",
            details={"transitions": sorted(invalid_keys)},
        )
    for key, gate in gates.items():
        if not isinstance(gate, dict):
            raise ValidationError(f"human_gates.{key} must be an object")
        require_exact_keys(
            gate,
            {"required_roles", "minimum_approvals"},
            f"human_gates.{key}",
        )
        roles = _validate_string_list(
            gate["required_roles"],
            f"human_gates.{key}.required_roles",
            pattern=ROLE_PATTERN,
            allow_empty=False,
        )
        minimum = gate["minimum_approvals"]
        _validate_limit(minimum, f"human_gates.{key}.minimum_approvals", 1, 20)
        if minimum < len(roles):
            raise ValidationError(
                "minimum_approvals cannot be lower than required role coverage",
                details={"transition": key},
            )

    for source, target in HIGH_IMPACT_TRANSITIONS:
        key = transition_key(source, target)
        mandatory = MANDATORY_GATE_CONTROLS[key]
        if key not in gates:
            raise ValidationError(
                "a mandatory high-impact human gate is missing",
                code="mandatory_gate_missing",
                details={"transition": key},
            )
        configured_roles = set(gates[key]["required_roles"])
        if not mandatory["required_roles"].issubset(configured_roles):
            raise ValidationError(
                "a mandatory high-impact gate role cannot be removed",
                code="mandatory_gate_weakened",
                details={
                    "transition": key,
                    "required_roles": sorted(mandatory["required_roles"]),
                },
            )
        if gates[key]["minimum_approvals"] < mandatory["minimum_approvals"]:
            raise ValidationError(
                "a mandatory high-impact gate approval count cannot be reduced",
                code="mandatory_gate_weakened",
                details={"transition": key},
            )

    permissions = policy["agent_permissions"]
    if not isinstance(permissions, dict):
        raise ValidationError("agent_permissions must be an object")
    require_exact_keys(permissions, AGENT_PERMISSION_KEYS, "agent_permissions")
    if any(not isinstance(value, bool) for value in permissions.values()):
        raise ValidationError("agent_permissions values must be booleans")
    enabled_denied = sorted(
        operation for operation in HARD_DENIED_AGENT_OPERATIONS if permissions[operation]
    )
    if enabled_denied:
        raise ValidationError(
            "hard-denied agent operations cannot be enabled",
            code="unsafe_agent_permission",
            details={"operations": enabled_denied},
        )

    transition_controls = policy["transition_controls"]
    if not isinstance(transition_controls, dict):
        raise ValidationError("transition_controls must be an object")
    require_exact_keys(
        transition_controls,
        {
            "require_independent_approval",
            "require_human_approval_for_all_transitions",
            "block_with_open_assignments",
        },
        "transition_controls",
    )
    if any(not isinstance(value, bool) for value in transition_controls.values()):
        raise ValidationError("transition_controls values must be booleans")
    if not transition_controls["require_independent_approval"]:
        raise ValidationError(
            "independent approval is a mandatory safety invariant",
            code="unsafe_transition_control",
        )
    if not transition_controls["require_human_approval_for_all_transitions"]:
        raise ValidationError(
            "human approval for transitions is a mandatory safety invariant",
            code="unsafe_transition_control",
        )

    artifact_controls = policy["artifact_controls"]
    if not isinstance(artifact_controls, dict):
        raise ValidationError("artifact_controls must be an object")
    require_exact_keys(
        artifact_controls,
        {"digest_algorithm", "agent_submission_requires_active_assignment"},
        "artifact_controls",
    )
    if artifact_controls["digest_algorithm"] != "sha256":
        raise ValidationError("sha256 is the only supported artifact digest algorithm")
    if not isinstance(
        artifact_controls["agent_submission_requires_active_assignment"], bool
    ):
        raise ValidationError(
            "agent_submission_requires_active_assignment must be a boolean"
        )

    limits = policy["limits"]
    if not isinstance(limits, dict):
        raise ValidationError("limits must be an object")
    require_exact_keys(
        limits,
        {"max_artifacts", "max_open_assignments", "max_pending_proposals"},
        "limits",
    )
    _validate_limit(limits["max_artifacts"], "limits.max_artifacts", 1, 100000)
    _validate_limit(
        limits["max_open_assignments"],
        "limits.max_open_assignments",
        1,
        10000,
    )
    _validate_limit(
        limits["max_pending_proposals"],
        "limits.max_pending_proposals",
        1,
        1000,
    )
    return copy.deepcopy(policy)
