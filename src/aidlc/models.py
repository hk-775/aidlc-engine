"""Core value objects and structural validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from aidlc.errors import ValidationError

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


def validate_stage(stage: str) -> str:
    if stage not in STAGES:
        raise ValidationError(
            "stage is not part of the AIDLC lifecycle",
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
        if self.kind not in {"human", "agent"}:
            raise ValidationError(
                "actor kind must be human or agent",
                details={"kind": self.kind},
            )
        normalized_roles = tuple(sorted(set(self.roles)))
        for role in normalized_roles:
            _validate_identifier(role, "role", ROLE_PATTERN)
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
    if not isinstance(state["revision"], int) or state["revision"] < 0:
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
    if not TIMESTAMP_PATTERN.fullmatch(project["created_at"]):
        raise ValidationError("project.created_at must be a UTC ISO-8601 timestamp")
    _validate_identifier(project["created_by"], "project.created_by", ID_PATTERN)

    for collection_name in (
        "artifacts",
        "assignments",
        "transition_proposals",
        "risk_decisions",
    ):
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

    audit = state["audit"]
    if not isinstance(audit, dict):
        raise ValidationError("audit must be an object")
    require_exact_keys(audit, {"event_count", "head_hash"}, "audit")
    if not isinstance(audit["event_count"], int) or audit["event_count"] < 1:
        raise ValidationError("audit.event_count must be a positive integer")
    if not isinstance(audit["head_hash"], str) or not HASH_PATTERN.fullmatch(
        audit["head_hash"]
    ):
        raise ValidationError("audit.head_hash must be a lowercase SHA-256 digest")
