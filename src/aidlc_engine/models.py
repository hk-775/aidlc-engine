"""Core value objects and structural validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Iterable

from aidlc_engine.errors import ValidationError

STAGES = (
    "discovery",
    "requirements",
    "design",
    "implementation",
    "verification",
    "release",
)

ADJACENT_TRANSITIONS = tuple(zip(STAGES, STAGES[1:]))
HIGH_IMPACT_TRANSITIONS = {
    ("design", "implementation"),
    ("verification", "release"),
}

GOVERNANCE_ROLES = {
    "project_owner",
    "technical_reviewer",
    "release_manager",
    "risk_owner",
}

HARD_DENIED_AGENT_OPERATIONS = {
    "merge",
    "deploy",
    "release",
    "accept_risk",
    "approve_transition",
    "satisfy_human_gate",
    "bypass_gate",
}

AGENT_PERMISSION_KEYS = {
    "propose_work",
    "submit_artifact",
    "complete_assigned_work",
    "propose_transition",
    *HARD_DENIED_AGENT_OPERATIONS,
}

ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
ROLE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
ARTIFACT_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$"
)
LOCATOR_MAX_LENGTH = 1024


def _validate_identifier(value: str, label: str, pattern: re.Pattern[str]) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ValidationError(
            f"{label} must use lowercase letters, digits, underscores, or hyphens",
            details={"field": label, "value": value},
        )
    return value


def validate_text(value: str, label: str, *, minimum: int = 1, maximum: int = 500) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be a string", details={"field": label})
    normalized = value.strip()
    if not minimum <= len(normalized) <= maximum:
        raise ValidationError(
            f"{label} length must be between {minimum} and {maximum}",
            details={"field": label, "length": len(normalized)},
        )
    if any(ord(character) < 32 and character not in "\t\n" for character in normalized):
        raise ValidationError(
            f"{label} contains unsupported control characters",
            details={"field": label},
        )
    return normalized


def validate_locator(locator: str) -> str:
    if not isinstance(locator, str):
        raise ValidationError("artifact locator must be a string")
    locator = locator.strip()
    if not locator:
        return ""
    if len(locator) > LOCATOR_MAX_LENGTH:
        raise ValidationError(
            f"artifact locator cannot exceed {LOCATOR_MAX_LENGTH} characters"
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in locator):
        raise ValidationError("artifact locator contains unsupported control characters")
    if "\\" in locator:
        raise ValidationError("artifact locator must use portable forward slashes")
    path = PurePosixPath(locator)
    segments = locator.split("/")
    if (
        path.is_absolute()
        or not path.parts
        or any(segment in {"", ".", ".."} for segment in segments)
    ):
        raise ValidationError("artifact locator must be a normalized safe relative path")
    if ":" in segments[0]:
        raise ValidationError("network and scheme-based artifact locators are unsupported")
    return locator


def validate_stage(stage: str) -> str:
    if stage not in STAGES:
        raise ValidationError(
            "stage is not part of the AI-DLC lifecycle",
            details={"stage": stage, "allowed": list(STAGES)},
        )
    return stage


def transition_key(source: str, target: str) -> str:
    validate_stage(source)
    validate_stage(target)
    return f"{source}->{target}"


def next_stage(stage: str) -> str | None:
    validate_stage(stage)
    index = STAGES.index(stage)
    return STAGES[index + 1] if index + 1 < len(STAGES) else None


@dataclass(frozen=True, slots=True)
class Actor:
    """A caller identity supplied by the embedding environment."""

    actor_id: str
    kind: str
    roles: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_identifier(self.actor_id, "actor_id", ID_PATTERN)
        if not isinstance(self.kind, str) or self.kind not in {"human", "agent"}:
            raise ValidationError(
                "actor kind must be human or agent",
                details={"kind": self.kind},
            )
        if not isinstance(self.roles, (list, tuple)) or any(
            not isinstance(role, str) for role in self.roles
        ):
            raise ValidationError("actor roles must be role identifiers")
        if len(self.roles) > 20:
            raise ValidationError("actor cannot hold more than 20 roles")
        for role in self.roles:
            _validate_identifier(role, "role", ROLE_PATTERN)
        normalized_roles = tuple(sorted(set(self.roles)))
        if self.kind == "agent" and GOVERNANCE_ROLES.intersection(normalized_roles):
            raise ValidationError(
                "agents cannot claim human governance roles",
                code="agent_governance_role_forbidden",
                details={"roles": sorted(GOVERNANCE_ROLES.intersection(normalized_roles))},
            )
        object.__setattr__(self, "roles", normalized_roles)

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.actor_id,
            "kind": self.kind,
            "roles": list(self.roles),
        }


def validate_actor_record(value: Any, label: str = "actor") -> Actor:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be an object")
    require_exact_keys(value, {"id", "kind", "roles"}, label)
    roles = value["roles"]
    if not isinstance(roles, list):
        raise ValidationError(f"{label}.roles must be an array")
    if len(roles) > 20:
        raise ValidationError(f"{label}.roles cannot contain more than 20 items")
    if any(not isinstance(role, str) for role in roles):
        raise ValidationError(f"{label}.roles must contain role identifiers")
    if len(roles) != len(set(roles)):
        raise ValidationError(f"{label}.roles must contain unique role identifiers")
    return Actor(value["id"], value["kind"], tuple(roles))


def require_exact_keys(
    value: dict[str, Any],
    expected: Iterable[str],
    label: str,
) -> None:
    expected_set = set(expected)
    actual_set = set(value)
    if actual_set != expected_set:
        raise ValidationError(
            f"{label} has unexpected or missing fields",
            details={
                "field": label,
                "missing": sorted(expected_set - actual_set),
                "unexpected": sorted(actual_set - expected_set),
            },
        )


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_timestamp(value: Any, label: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or not TIMESTAMP_PATTERN.fullmatch(value):
        raise ValidationError(f"{label} must be a UTC ISO-8601 timestamp")


def _validate_optional_identifier(value: Any, label: str) -> None:
    if value is not None:
        _validate_identifier(value, label, ID_PATTERN)


def _validate_identifier_list(
    value: Any,
    label: str,
    *,
    pattern: re.Pattern[str],
    allow_empty: bool = True,
) -> list[str]:
    if not isinstance(value, list):
        raise ValidationError(f"{label} must be an array")
    if not allow_empty and not value:
        raise ValidationError(f"{label} cannot be empty")
    if any(not isinstance(item, str) or not pattern.fullmatch(item) for item in value):
        raise ValidationError(f"{label} contains an invalid value")
    if len(value) != len(set(value)):
        raise ValidationError(f"{label} cannot contain duplicates")
    return value


def _validate_artifact(artifact: dict[str, Any], label: str) -> None:
    require_exact_keys(
        artifact,
        {
            "id",
            "stage",
            "artifact_type",
            "title",
            "digest",
            "locator",
            "assignment_id",
            "submitted_by",
            "submitted_at",
        },
        label,
    )
    _validate_identifier(artifact["id"], f"{label}.id", ID_PATTERN)
    validate_stage(artifact["stage"])
    _validate_identifier(
        artifact["artifact_type"],
        f"{label}.artifact_type",
        ARTIFACT_TYPE_PATTERN,
    )
    validate_text(artifact["title"], f"{label}.title", maximum=200)
    if not isinstance(artifact["digest"], str) or not DIGEST_PATTERN.fullmatch(
        artifact["digest"]
    ):
        raise ValidationError(f"{label}.digest must be a lowercase SHA-256 digest")
    normalized_locator = validate_locator(artifact["locator"])
    if normalized_locator != artifact["locator"]:
        raise ValidationError(f"{label}.locator must be normalized")
    _validate_optional_identifier(artifact["assignment_id"], f"{label}.assignment_id")
    _validate_identifier(artifact["submitted_by"], f"{label}.submitted_by", ID_PATTERN)
    _validate_timestamp(artifact["submitted_at"], f"{label}.submitted_at")


def _validate_assignment(assignment: dict[str, Any], label: str) -> None:
    require_exact_keys(
        assignment,
        {
            "id",
            "stage",
            "summary",
            "deliverable_types",
            "assignee_id",
            "status",
            "proposed_by",
            "approved_by",
            "created_at",
            "approved_at",
            "completed_at",
        },
        label,
    )
    _validate_identifier(assignment["id"], f"{label}.id", ID_PATTERN)
    validate_stage(assignment["stage"])
    validate_text(assignment["summary"], f"{label}.summary", maximum=500)
    _validate_identifier_list(
        assignment["deliverable_types"],
        f"{label}.deliverable_types",
        pattern=ARTIFACT_TYPE_PATTERN,
        allow_empty=False,
    )
    _validate_identifier(assignment["assignee_id"], f"{label}.assignee_id", ID_PATTERN)
    _validate_identifier(assignment["proposed_by"], f"{label}.proposed_by", ID_PATTERN)
    _validate_optional_identifier(assignment["approved_by"], f"{label}.approved_by")
    _validate_timestamp(assignment["created_at"], f"{label}.created_at")
    _validate_timestamp(
        assignment["approved_at"],
        f"{label}.approved_at",
        nullable=True,
    )
    _validate_timestamp(
        assignment["completed_at"],
        f"{label}.completed_at",
        nullable=True,
    )
    status = assignment["status"]
    if status not in {"proposed", "active", "completed"}:
        raise ValidationError(f"{label}.status is invalid")
    approved = assignment["approved_by"] is not None and assignment["approved_at"] is not None
    if status == "proposed" and (
        assignment["approved_by"] is not None
        or assignment["approved_at"] is not None
        or assignment["completed_at"] is not None
    ):
        raise ValidationError(f"{label} proposed status conflicts with approval fields")
    if status == "active" and (not approved or assignment["completed_at"] is not None):
        raise ValidationError(f"{label} active status requires approval only")
    if status == "completed" and (not approved or assignment["completed_at"] is None):
        raise ValidationError(f"{label} completed status requires approval and completion")


def _validate_approval(
    approval: Any,
    label: str,
    required_roles: list[str],
) -> tuple[str, str | None]:
    if not isinstance(approval, dict):
        raise ValidationError(f"{label} must be an object")
    require_exact_keys(approval, {"actor_id", "role", "approved_at"}, label)
    actor_id = _validate_identifier(approval["actor_id"], f"{label}.actor_id", ID_PATTERN)
    role = approval["role"]
    if role is not None:
        _validate_identifier(role, f"{label}.role", ROLE_PATTERN)
    if role is not None and required_roles and role not in required_roles:
        raise ValidationError(f"{label}.role is not required by the gate")
    if not required_roles and role is not None:
        raise ValidationError(f"{label}.role must be null for an ordinary gate")
    _validate_timestamp(approval["approved_at"], f"{label}.approved_at")
    return actor_id, role


def _validate_proposal(proposal: dict[str, Any], label: str) -> None:
    require_exact_keys(
        proposal,
        {
            "id",
            "source_stage",
            "target_stage",
            "rationale",
            "evidence_ids",
            "proposed_by",
            "proposed_by_kind",
            "status",
            "created_at",
            "resolved_at",
            "rejected_by",
            "rejection_reason",
            "gate",
        },
        label,
    )
    _validate_identifier(proposal["id"], f"{label}.id", ID_PATTERN)
    source = validate_stage(proposal["source_stage"])
    target = validate_stage(proposal["target_stage"])
    if next_stage(source) != target:
        raise ValidationError(f"{label} must describe an adjacent forward transition")
    validate_text(proposal["rationale"], f"{label}.rationale", maximum=1000)
    _validate_identifier_list(
        proposal["evidence_ids"],
        f"{label}.evidence_ids",
        pattern=ID_PATTERN,
    )
    _validate_identifier(proposal["proposed_by"], f"{label}.proposed_by", ID_PATTERN)
    if proposal["proposed_by_kind"] not in {"human", "agent"}:
        raise ValidationError(f"{label}.proposed_by_kind is invalid")
    _validate_timestamp(proposal["created_at"], f"{label}.created_at")
    _validate_timestamp(proposal["resolved_at"], f"{label}.resolved_at", nullable=True)
    _validate_optional_identifier(proposal["rejected_by"], f"{label}.rejected_by")
    if proposal["rejection_reason"] is not None:
        validate_text(
            proposal["rejection_reason"],
            f"{label}.rejection_reason",
            maximum=1000,
        )

    gate = proposal["gate"]
    if not isinstance(gate, dict):
        raise ValidationError(f"{label}.gate must be an object")
    require_exact_keys(
        gate,
        {"required_roles", "minimum_approvals", "approvals"},
        f"{label}.gate",
    )
    required_roles = _validate_identifier_list(
        gate["required_roles"],
        f"{label}.gate.required_roles",
        pattern=ROLE_PATTERN,
    )
    minimum = gate["minimum_approvals"]
    if not _is_integer(minimum) or not 1 <= minimum <= 20:
        raise ValidationError(
            f"{label}.gate.minimum_approvals must be an integer between 1 and 20"
        )
    if minimum < len(required_roles):
        raise ValidationError(
            f"{label}.gate.minimum_approvals cannot be lower than role coverage"
        )
    approvals = gate["approvals"]
    if not isinstance(approvals, list) or len(approvals) > 20:
        raise ValidationError(f"{label}.gate.approvals must be an array of at most 20 items")
    actor_ids: list[str] = []
    approval_roles: list[str] = []
    for index, approval in enumerate(approvals):
        actor_id, role = _validate_approval(
            approval,
            f"{label}.gate.approvals[{index}]",
            required_roles,
        )
        actor_ids.append(actor_id)
        if role is not None:
            approval_roles.append(role)
    if len(actor_ids) != len(set(actor_ids)):
        raise ValidationError(f"{label}.gate approvals require distinct actors")
    if len(approval_roles) != len(set(approval_roles)):
        raise ValidationError(f"{label}.gate approvals cannot duplicate required roles")
    if proposal["proposed_by"] in actor_ids:
        raise ValidationError(f"{label}.gate approvals cannot include the proposer")

    gate_complete = len(approvals) >= minimum and set(required_roles).issubset(
        approval_roles
    )
    status = proposal["status"]
    if status not in {"pending", "approved", "rejected"}:
        raise ValidationError(f"{label}.status is invalid")
    if status == "pending" and (
        proposal["resolved_at"] is not None
        or proposal["rejected_by"] is not None
        or proposal["rejection_reason"] is not None
        or gate_complete
    ):
        raise ValidationError(f"{label} pending status conflicts with resolution fields")
    if status == "approved" and (
        proposal["resolved_at"] is None
        or proposal["rejected_by"] is not None
        or proposal["rejection_reason"] is not None
        or not gate_complete
    ):
        raise ValidationError(f"{label} approved status requires a complete gate")
    if status == "rejected" and (
        proposal["resolved_at"] is None
        or proposal["rejected_by"] is None
        or proposal["rejection_reason"] is None
    ):
        raise ValidationError(f"{label} rejected status requires rejection details")


def _validate_risk_decision(decision: dict[str, Any], label: str) -> None:
    require_exact_keys(
        decision,
        {"id", "title", "decision", "rationale", "decided_by", "decided_at"},
        label,
    )
    _validate_identifier(decision["id"], f"{label}.id", ID_PATTERN)
    validate_text(decision["title"], f"{label}.title", maximum=200)
    if decision["decision"] != "accepted":
        raise ValidationError(f"{label}.decision must be accepted")
    validate_text(decision["rationale"], f"{label}.rationale", maximum=1000)
    _validate_identifier(decision["decided_by"], f"{label}.decided_by", ID_PATTERN)
    _validate_timestamp(decision["decided_at"], f"{label}.decided_at")


def validate_state(state: dict[str, Any]) -> None:
    if not isinstance(state, dict):
        raise ValidationError("project state must be an object")
    require_exact_keys(
        state,
        {
            "schema_version",
            "project",
            "policy_digest",
            "current_stage",
            "revision",
            "artifacts",
            "assignments",
            "transition_proposals",
            "risk_decisions",
            "audit",
        },
        "state",
    )
    if state["schema_version"] != 1:
        raise ValidationError("unsupported project state schema version")
    validate_stage(state["current_stage"])
    if not _is_integer(state["revision"]) or state["revision"] < 0:
        raise ValidationError("state revision must be a non-negative integer")
    if not isinstance(state["policy_digest"], str) or not HASH_PATTERN.fullmatch(
        state["policy_digest"]
    ):
        raise ValidationError("policy_digest must be a lowercase SHA-256 digest")

    project = state["project"]
    if not isinstance(project, dict):
        raise ValidationError("project must be an object")
    require_exact_keys(
        project,
        {"id", "name", "description", "created_at", "created_by"},
        "project",
    )
    _validate_identifier(project["id"], "project.id", ID_PATTERN)
    validate_text(project["name"], "project.name", maximum=120)
    validate_text(project["description"], "project.description", minimum=0, maximum=1000)
    _validate_timestamp(project["created_at"], "project.created_at")
    _validate_identifier(project["created_by"], "project.created_by", ID_PATTERN)

    validators = {
        "artifacts": _validate_artifact,
        "assignments": _validate_assignment,
        "transition_proposals": _validate_proposal,
        "risk_decisions": _validate_risk_decision,
    }
    for collection_name, validator in validators.items():
        collection = state[collection_name]
        if not isinstance(collection, dict):
            raise ValidationError(f"{collection_name} must be an object")
        for key, item in collection.items():
            _validate_identifier(key, f"{collection_name} key", ID_PATTERN)
            if not isinstance(item, dict) or item.get("id") != key:
                raise ValidationError(
                    f"{collection_name} entries must be objects keyed by their id",
                    details={"collection": collection_name, "id": key},
                )
            validator(item, f"{collection_name}.{key}")

    for artifact_id, artifact in state["artifacts"].items():
        assignment_id = artifact["assignment_id"]
        if assignment_id is not None and assignment_id not in state["assignments"]:
            raise ValidationError(
                "artifact references an unknown assignment",
                details={"artifact_id": artifact_id, "assignment_id": assignment_id},
            )
    for proposal_id, proposal in state["transition_proposals"].items():
        missing_evidence = sorted(
            set(proposal["evidence_ids"]) - set(state["artifacts"])
        )
        if missing_evidence:
            raise ValidationError(
                "transition proposal references unknown evidence",
                details={"proposal_id": proposal_id, "evidence_ids": missing_evidence},
            )

    audit = state["audit"]
    if not isinstance(audit, dict):
        raise ValidationError("audit must be an object")
    require_exact_keys(audit, {"event_count", "head_hash"}, "audit")
    if not _is_integer(audit["event_count"]) or audit["event_count"] < 1:
        raise ValidationError("audit.event_count must be a positive integer")
    if not isinstance(audit["head_hash"], str) or not HASH_PATTERN.fullmatch(
        audit["head_hash"]
    ):
        raise ValidationError("audit.head_hash must be a lowercase SHA-256 digest")
