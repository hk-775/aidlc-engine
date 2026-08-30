"""Human-governed lifecycle operations."""

from __future__ import annotations

import hashlib
from pathlib import PurePosixPath
from typing import Any

from aidlc.errors import (
    AuthorizationError,
    ConflictError,
    ForbiddenOperationError,
    NotFoundError,
    ValidationError,
)
from aidlc.models import (
    ARTIFACT_TYPE_PATTERN,
    DIGEST_PATTERN,
    HARD_DENIED_AGENT_OPERATIONS,
    ID_PATTERN,
    Actor,
    next_stage,
    transition_key,
    validate_stage,
    validate_text,
)
from aidlc.persistence import JsonProjectRepository, MutationResult
from aidlc.policy import default_policy


def sha256_digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


class LifecycleService:
    """Application service that enforces policy before each state mutation."""

    def __init__(self, repository: JsonProjectRepository) -> None:
        self.repository = repository

    def initialize(
        self,
        *,
        name: str,
        description: str,
        creator: Actor,
        policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.repository.initialize(
            name=name,
            description=description,
            creator=creator,
            policy=policy or default_policy(),
        )

    @staticmethod
    def _require_human(actor: Actor, action: str) -> None:
        if actor.kind != "human":
            raise AuthorizationError(
                f"{action} requires a human actor",
                code="human_actor_required",
                details={"action": action, "actor_id": actor.actor_id},
            )

    @staticmethod
    def _require_agent_permission(
        actor: Actor,
        policy: dict[str, Any],
        operation: str,
    ) -> None:
        if actor.kind != "agent":
            return
        if operation in HARD_DENIED_AGENT_OPERATIONS:
            raise ForbiddenOperationError(
                "the operation is permanently denied to agents",
                details={"operation": operation, "actor_id": actor.actor_id},
            )
        if not policy["agent_permissions"].get(operation, False):
            raise AuthorizationError(
                "policy does not grant this agent operation",
                code="agent_permission_disabled",
                details={"operation": operation, "actor_id": actor.actor_id},
            )

    @staticmethod
    def _validate_artifact_type(artifact_type: str) -> str:
        if not isinstance(artifact_type, str) or not ARTIFACT_TYPE_PATTERN.fullmatch(
            artifact_type
        ):
            raise ValidationError(
                "artifact type must use lowercase letters, digits, and underscores",
                details={"artifact_type": artifact_type},
            )
        return artifact_type

    @staticmethod
    def _validate_digest(digest: str) -> str:
        if not isinstance(digest, str) or not DIGEST_PATTERN.fullmatch(digest):
            raise ValidationError(
                "artifact digest must be sha256 followed by 64 lowercase hex characters"
            )
        return digest

    @staticmethod
    def _validate_locator(locator: str) -> str:
        if not isinstance(locator, str):
            raise ValidationError("artifact locator must be a string")
        locator = locator.strip()
        if not locator:
            return ""
        if "\\" in locator:
            raise ValidationError("artifact locator must use portable forward slashes")
        path = PurePosixPath(locator)
        if path.is_absolute() or ".." in path.parts:
            raise ValidationError("artifact locator must be a safe relative path")
        if ":" in path.parts[0]:
            raise ValidationError("network and scheme-based artifact locators are unsupported")
        return locator

    def propose_work(
        self,
        *,
        actor: Actor,
        assignee_id: str,
        stage: str,
        summary: str,
        deliverable_types: list[str],
    ) -> dict[str, Any]:
        validate_stage(stage)
        if not isinstance(assignee_id, str) or not ID_PATTERN.fullmatch(assignee_id):
            raise ValidationError(
                "assignee_id must be a portable actor identifier",
                details={"assignee_id": assignee_id},
            )
        summary = validate_text(summary, "summary", maximum=500)
        normalized_deliverables = []
        for item in deliverable_types:
            normalized_deliverables.append(self._validate_artifact_type(item))
        if not normalized_deliverables:
            raise ValidationError("at least one deliverable type is required")
        if len(normalized_deliverables) != len(set(normalized_deliverables)):
            raise ValidationError("deliverable types cannot contain duplicates")

        def mutation(state: dict[str, Any], policy: dict[str, Any], values: Any) -> MutationResult:
            self._require_agent_permission(actor, policy, "propose_work")
            if stage != state["current_stage"]:
                raise ConflictError(
                    "work can only be proposed for the current stage",
                    details={"current_stage": state["current_stage"], "stage": stage},
                )
            if actor.kind == "agent" and assignee_id != actor.actor_id:
                raise AuthorizationError(
                    "an agent may only propose work for itself",
                    code="agent_cannot_assign_peer",
                )
            open_count = sum(
                assignment["status"] in {"proposed", "active"}
                for assignment in state["assignments"].values()
            )
            if open_count >= policy["limits"]["max_open_assignments"]:
                raise ConflictError("the open assignment limit has been reached")
            assignment_id = values.identifier(
                "work",
                f"{actor.actor_id}:{assignee_id}:{stage}:{summary}",
            )
            assignment = {
                "id": assignment_id,
                "stage": stage,
                "summary": summary,
                "deliverable_types": normalized_deliverables,
                "assignee_id": assignee_id,
                "status": "proposed",
                "proposed_by": actor.actor_id,
                "approved_by": None,
                "created_at": values.timestamp,
                "approved_at": None,
                "completed_at": None,
            }
            state["assignments"][assignment_id] = assignment
            return MutationResult(
                event_type="work.proposed",
                payload={
                    "assignment_id": assignment_id,
                    "assignee_id": assignee_id,
                    "stage": stage,
                    "deliverable_types": normalized_deliverables,
                },
                result={"assignment": assignment},
            )

        return self.repository.mutate(actor, mutation)

    def approve_work(self, *, actor: Actor, assignment_id: str) -> dict[str, Any]:
        self._require_human(actor, "work approval")

        def mutation(state: dict[str, Any], policy: dict[str, Any], values: Any) -> MutationResult:
            del policy
            assignment = state["assignments"].get(assignment_id)
            if assignment is None:
                raise NotFoundError("work assignment was not found")
            if assignment["status"] != "proposed":
                raise ConflictError("only proposed work can be approved")
            if assignment["proposed_by"] == actor.actor_id:
                raise AuthorizationError(
                    "a proposer cannot approve the same work assignment",
                    code="self_approval_forbidden",
                )
            if assignment["stage"] != state["current_stage"]:
                raise ConflictError("work assignment is not for the current stage")
            assignment["status"] = "active"
            assignment["approved_by"] = actor.actor_id
            assignment["approved_at"] = values.timestamp
            return MutationResult(
                event_type="work.approved",
                payload={
                    "assignment_id": assignment_id,
                    "assignee_id": assignment["assignee_id"],
                },
                result={"assignment": assignment},
            )

        return self.repository.mutate(actor, mutation)

    def complete_work(self, *, actor: Actor, assignment_id: str) -> dict[str, Any]:
        def mutation(state: dict[str, Any], policy: dict[str, Any], values: Any) -> MutationResult:
            self._require_agent_permission(actor, policy, "complete_assigned_work")
            assignment = state["assignments"].get(assignment_id)
            if assignment is None:
                raise NotFoundError("work assignment was not found")
            if assignment["status"] != "active":
                raise ConflictError("only active work can be completed")
            if assignment["assignee_id"] != actor.actor_id:
                raise AuthorizationError(
                    "only the named assignee can complete work",
                    code="assignment_assignee_required",
                )
            if assignment["stage"] != state["current_stage"]:
                raise ConflictError("work assignment is not for the current stage")
            submitted_types = {
                artifact["artifact_type"]
                for artifact in state["artifacts"].values()
                if artifact["stage"] == assignment["stage"]
                and artifact["submitted_by"] == actor.actor_id
                and artifact["assignment_id"] == assignment_id
            }
            missing = sorted(set(assignment["deliverable_types"]) - submitted_types)
            if missing:
                raise ConflictError(
                    "work cannot complete until every deliverable is registered",
                    code="assignment_deliverables_missing",
                    details={"missing_artifact_types": missing},
                )
            assignment["status"] = "completed"
            assignment["completed_at"] = values.timestamp
            return MutationResult(
                event_type="work.completed",
                payload={"assignment_id": assignment_id},
                result={"assignment": assignment},
            )

        return self.repository.mutate(actor, mutation)

    def register_artifact(
        self,
        *,
        actor: Actor,
        artifact_type: str,
        title: str,
        digest: str,
        locator: str = "",
        assignment_id: str | None = None,
    ) -> dict[str, Any]:
        artifact_type = self._validate_artifact_type(artifact_type)
        title = validate_text(title, "title", maximum=200)
        digest = self._validate_digest(digest)
        locator = self._validate_locator(locator)

        def mutation(state: dict[str, Any], policy: dict[str, Any], values: Any) -> MutationResult:
            self._require_agent_permission(actor, policy, "submit_artifact")
            if len(state["artifacts"]) >= policy["limits"]["max_artifacts"]:
                raise ConflictError("the artifact limit has been reached")
            for existing in state["artifacts"].values():
                if (
                    existing["stage"] == state["current_stage"]
                    and existing["artifact_type"] == artifact_type
                    and existing["digest"] == digest
                ):
                    raise ConflictError(
                        "the same artifact digest is already registered for this stage",
                        code="duplicate_artifact",
                    )
            if actor.kind == "agent" and policy["artifact_controls"][
                "agent_submission_requires_active_assignment"
            ]:
                if assignment_id is None:
                    raise AuthorizationError(
                        "agent artifact submissions require an active assignment",
                        code="active_assignment_required",
                    )
                assignment = state["assignments"].get(assignment_id)
                if (
                    assignment is None
                    or assignment["status"] != "active"
                    or assignment["assignee_id"] != actor.actor_id
                    or assignment["stage"] != state["current_stage"]
                    or artifact_type not in assignment["deliverable_types"]
                ):
                    raise AuthorizationError(
                        "the assignment does not authorize this artifact submission",
                        code="assignment_scope_mismatch",
                    )
            elif assignment_id is not None and assignment_id not in state["assignments"]:
                raise NotFoundError("work assignment was not found")
            artifact_id = values.identifier(
                "artifact",
                f"{state['current_stage']}:{artifact_type}:{digest}",
            )
            artifact = {
                "id": artifact_id,
                "stage": state["current_stage"],
                "artifact_type": artifact_type,
                "title": title,
                "digest": digest,
                "locator": locator,
                "assignment_id": assignment_id,
                "submitted_by": actor.actor_id,
                "submitted_at": values.timestamp,
            }
            state["artifacts"][artifact_id] = artifact
            return MutationResult(
                event_type="artifact.registered",
                payload={
                    "artifact_id": artifact_id,
                    "artifact_type": artifact_type,
                    "stage": state["current_stage"],
                    "digest": digest,
                    "assignment_id": assignment_id,
                },
                result={"artifact": artifact},
            )

        return self.repository.mutate(actor, mutation)

    @staticmethod
    def _missing_evidence(
        state: dict[str, Any],
        policy: dict[str, Any],
        evidence_ids: list[str],
    ) -> tuple[list[str], list[str]]:
        evidence = []
        missing_ids = []
        for artifact_id in evidence_ids:
            artifact = state["artifacts"].get(artifact_id)
            if artifact is None:
                missing_ids.append(artifact_id)
            elif artifact["stage"] != state["current_stage"]:
                missing_ids.append(artifact_id)
            else:
                evidence.append(artifact)
        required_types = set(policy["required_artifacts"][state["current_stage"]])
        supplied_types = {artifact["artifact_type"] for artifact in evidence}
        return sorted(required_types - supplied_types), sorted(missing_ids)

    @staticmethod
    def _open_assignments(state: dict[str, Any]) -> list[str]:
        return sorted(
            assignment_id
            for assignment_id, assignment in state["assignments"].items()
            if assignment["stage"] == state["current_stage"]
            and assignment["status"] in {"proposed", "active"}
        )

    def propose_transition(
        self,
        *,
        actor: Actor,
        rationale: str,
        evidence_ids: list[str],
    ) -> dict[str, Any]:
        rationale = validate_text(rationale, "rationale", maximum=1000)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValidationError("evidence ids cannot contain duplicates")

        def mutation(state: dict[str, Any], policy: dict[str, Any], values: Any) -> MutationResult:
            self._require_agent_permission(actor, policy, "propose_transition")
            target = next_stage(state["current_stage"])
            if target is None:
                raise ConflictError("release is the terminal lifecycle stage")
            pending_count = sum(
                proposal["status"] == "pending"
                for proposal in state["transition_proposals"].values()
            )
            if pending_count >= policy["limits"]["max_pending_proposals"]:
                raise ConflictError("the pending transition proposal limit has been reached")
            if pending_count:
                raise ConflictError(
                    "a transition proposal is already pending",
                    code="pending_transition_exists",
                )
            missing_types, missing_ids = self._missing_evidence(
                state,
                policy,
                evidence_ids,
            )
            if missing_types or missing_ids:
                raise ConflictError(
                    "transition evidence requirements are not satisfied",
                    code="evidence_requirements_unsatisfied",
                    details={
                        "missing_artifact_types": missing_types,
                        "invalid_evidence_ids": missing_ids,
                    },
                )
            if policy["transition_controls"]["block_with_open_assignments"]:
                open_assignments = self._open_assignments(state)
                if open_assignments:
                    raise ConflictError(
                        "open assignments block the stage transition",
                        code="open_assignments_block_transition",
                        details={"assignment_ids": open_assignments},
                    )
            key = transition_key(state["current_stage"], target)
            configured_gate = policy["human_gates"].get(key)
            if configured_gate:
                required_roles = list(configured_gate["required_roles"])
                minimum_approvals = configured_gate["minimum_approvals"]
            else:
                required_roles = []
                minimum_approvals = 1
            proposal_id = values.identifier(
                "proposal",
                f"{key}:{actor.actor_id}:{rationale}",
            )
            proposal = {
                "id": proposal_id,
                "source_stage": state["current_stage"],
                "target_stage": target,
                "rationale": rationale,
                "evidence_ids": list(evidence_ids),
                "proposed_by": actor.actor_id,
                "proposed_by_kind": actor.kind,
                "status": "pending",
                "created_at": values.timestamp,
                "resolved_at": None,
                "rejected_by": None,
                "rejection_reason": None,
                "gate": {
                    "required_roles": required_roles,
                    "minimum_approvals": minimum_approvals,
                    "approvals": [],
                },
            }
            state["transition_proposals"][proposal_id] = proposal
            return MutationResult(
                event_type="transition.proposed",
                payload={
                    "proposal_id": proposal_id,
                    "source_stage": proposal["source_stage"],
                    "target_stage": target,
                    "evidence_ids": list(evidence_ids),
                    "required_roles": required_roles,
                    "minimum_approvals": minimum_approvals,
                },
                result={"proposal": proposal},
            )

        return self.repository.mutate(actor, mutation)

    def approve_transition(
        self,
        *,
        actor: Actor,
        proposal_id: str,
        approval_role: str | None = None,
    ) -> dict[str, Any]:
        self._require_human(actor, "transition approval")
        requested_role = approval_role

        def mutation(state: dict[str, Any], policy: dict[str, Any], values: Any) -> MutationResult:
            proposal = state["transition_proposals"].get(proposal_id)
            if proposal is None:
                raise NotFoundError("transition proposal was not found")
            if proposal["status"] != "pending":
                raise ConflictError("only pending transition proposals can be approved")
            if proposal["proposed_by"] == actor.actor_id:
                raise AuthorizationError(
                    "a proposer cannot approve its own transition proposal",
                    code="self_approval_forbidden",
                )
            if proposal["source_stage"] != state["current_stage"]:
                raise ConflictError("transition proposal no longer matches project stage")
            if any(
                approval["actor_id"] == actor.actor_id
                for approval in proposal["gate"]["approvals"]
            ):
                raise ConflictError("this actor already approved the proposal")
            missing_types, missing_ids = self._missing_evidence(
                state,
                policy,
                proposal["evidence_ids"],
            )
            if missing_types or missing_ids:
                raise ConflictError(
                    "transition evidence no longer satisfies policy",
                    code="evidence_requirements_unsatisfied",
                    details={
                        "missing_artifact_types": missing_types,
                        "invalid_evidence_ids": missing_ids,
                    },
                )
            if policy["transition_controls"]["block_with_open_assignments"]:
                open_assignments = self._open_assignments(state)
                if open_assignments:
                    raise ConflictError(
                        "open assignments block the stage transition",
                        code="open_assignments_block_transition",
                        details={"assignment_ids": open_assignments},
                    )
            required_roles = proposal["gate"]["required_roles"]
            if required_roles:
                approved_roles = {
                    approval["role"]
                    for approval in proposal["gate"]["approvals"]
                    if approval["role"] is not None
                }
                uncovered_roles = set(required_roles) - approved_roles
                if requested_role is None and uncovered_roles:
                    raise AuthorizationError(
                        "approval must name an uncovered required gate role",
                        code="gate_role_required",
                        details={"required_roles": sorted(uncovered_roles)},
                    )
                if requested_role is not None and requested_role not in required_roles:
                    raise AuthorizationError(
                        "approval role is not part of this gate",
                        code="gate_role_required",
                        details={"required_roles": required_roles},
                    )
                if requested_role is not None and not actor.has_role(requested_role):
                    raise AuthorizationError(
                        "actor does not hold the selected gate role",
                        code="gate_role_not_held",
                        details={"role": requested_role},
                    )
                if requested_role is not None and any(
                    approval["role"] == requested_role
                    for approval in proposal["gate"]["approvals"]
                ):
                    raise ConflictError(
                        "the selected gate role is already represented",
                        code="gate_role_already_approved",
                    )
                selected_role = requested_role
            else:
                if requested_role is not None:
                    raise ValidationError(
                        "approval role is not used by this transition gate",
                        details={"approval_role": requested_role},
                    )
                selected_role = None
            approval = {
                "actor_id": actor.actor_id,
                "role": selected_role,
                "approved_at": values.timestamp,
            }
            proposal["gate"]["approvals"].append(approval)
            approved_roles = {
                item["role"]
                for item in proposal["gate"]["approvals"]
                if item["role"] is not None
            }
            gate_complete = (
                len(proposal["gate"]["approvals"])
                >= proposal["gate"]["minimum_approvals"]
                and set(required_roles).issubset(approved_roles)
            )
            if gate_complete:
                proposal["status"] = "approved"
                proposal["resolved_at"] = values.timestamp
                state["current_stage"] = proposal["target_stage"]
                event_type = "transition.executed"
            else:
                event_type = "transition.approval_recorded"
            return MutationResult(
                event_type=event_type,
                payload={
                    "proposal_id": proposal_id,
                    "approval": approval,
                    "gate_complete": gate_complete,
                    "current_stage": state["current_stage"],
                },
                result={
                    "proposal": proposal,
                    "transition_executed": gate_complete,
                    "current_stage": state["current_stage"],
                },
            )

        return self.repository.mutate(actor, mutation)

    def reject_transition(
        self,
        *,
        actor: Actor,
        proposal_id: str,
        reason: str,
    ) -> dict[str, Any]:
        self._require_human(actor, "transition rejection")
        reason = validate_text(reason, "reason", maximum=1000)

        def mutation(state: dict[str, Any], policy: dict[str, Any], values: Any) -> MutationResult:
            del policy
            proposal = state["transition_proposals"].get(proposal_id)
            if proposal is None:
                raise NotFoundError("transition proposal was not found")
            if proposal["status"] != "pending":
                raise ConflictError("only pending transition proposals can be rejected")
            proposal["status"] = "rejected"
            proposal["resolved_at"] = values.timestamp
            proposal["rejected_by"] = actor.actor_id
            proposal["rejection_reason"] = reason
            return MutationResult(
                event_type="transition.rejected",
                payload={"proposal_id": proposal_id, "reason": reason},
                result={"proposal": proposal},
            )

        return self.repository.mutate(actor, mutation)

    def record_risk_acceptance(
        self,
        *,
        actor: Actor,
        title: str,
        rationale: str,
    ) -> dict[str, Any]:
        self._require_human(actor, "risk acceptance")
        if not actor.has_role("risk_owner"):
            raise AuthorizationError(
                "risk acceptance requires the risk_owner role",
                code="risk_owner_required",
            )
        title = validate_text(title, "title", maximum=200)
        rationale = validate_text(rationale, "rationale", maximum=1000)

        def mutation(state: dict[str, Any], policy: dict[str, Any], values: Any) -> MutationResult:
            del policy
            decision_id = values.identifier("risk", f"{title}:{actor.actor_id}")
            decision = {
                "id": decision_id,
                "title": title,
                "decision": "accepted",
                "rationale": rationale,
                "decided_by": actor.actor_id,
                "decided_at": values.timestamp,
            }
            state["risk_decisions"][decision_id] = decision
            return MutationResult(
                event_type="risk.accepted",
                payload={"decision_id": decision_id, "title": title},
                result={"risk_decision": decision},
            )

        return self.repository.mutate(actor, mutation)

    def guard_operation(self, *, actor: Actor, operation: str) -> dict[str, Any]:
        known_operations = {
            "propose_work",
            "submit_artifact",
            "complete_assigned_work",
            "propose_transition",
            *HARD_DENIED_AGENT_OPERATIONS,
        }
        if operation not in known_operations:
            raise ValidationError(
                "operation is not recognized",
                details={"operation": operation, "known_operations": sorted(known_operations)},
            )
        policy = self.repository.load_policy()
        if actor.kind == "agent":
            self._require_agent_permission(actor, policy, operation)
            return {"authorized": True, "operation": operation, "actor": actor.to_dict()}
        if operation in {"merge", "deploy", "release", "bypass_gate", "satisfy_human_gate"}:
            raise ForbiddenOperationError(
                "AIDLC does not execute or bypass external delivery actions",
                code="external_execution_not_supported",
                details={"operation": operation},
            )
        if operation == "accept_risk" and not actor.has_role("risk_owner"):
            raise AuthorizationError(
                "risk acceptance requires the risk_owner role",
                code="risk_owner_required",
            )
        return {"authorized": True, "operation": operation, "actor": actor.to_dict()}
