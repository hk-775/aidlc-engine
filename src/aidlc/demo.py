"""Deterministic, industry-neutral demonstration workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aidlc.models import Actor, STAGES
from aidlc.persistence import JsonProjectRepository
from aidlc.policy import default_policy
from aidlc.service import LifecycleService, sha256_digest
from aidlc.values import DeterministicValueProvider


def run_demo(store: str | Path) -> dict[str, Any]:
    provider = DeterministicValueProvider(
        seed="aidlc-synthetic-demo-v1",
        base_time=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
    )
    repository = JsonProjectRepository(store, provider)
    service = LifecycleService(repository)
    coordinator = Actor("human_coordinator", "human", ("project_owner",))
    reviewer = Actor("human_reviewer", "human", ("technical_reviewer",))
    release_manager = Actor("human_release_manager", "human", ("release_manager",))
    risk_owner = Actor("human_risk_owner", "human", ("risk_owner",))
    agent = Actor("agent_builder", "agent")

    policy = default_policy()
    service.initialize(
        name="Civic Forms Pilot",
        description="Synthetic workflow for a generic document intake service.",
        creator=coordinator,
        policy=policy,
    )

    artifact_ids: list[str] = []
    for stage in STAGES[:-1]:
        artifact_type = policy["required_artifacts"][stage][0]
        work = service.propose_work(
            actor=agent,
            assignee_id=agent.actor_id,
            stage=stage,
            summary=f"Prepare the required {stage} evidence",
            deliverable_types=[artifact_type],
        )["assignment"]
        service.approve_work(actor=coordinator, assignment_id=work["id"])
        content = (
            f"Synthetic {stage} evidence for the Civic Forms Pilot.\n"
            "This example contains no customer or production data.\n"
        ).encode()
        artifact = service.register_artifact(
            actor=agent,
            artifact_type=artifact_type,
            title=f"{stage.title()} evidence",
            digest=sha256_digest(content),
            locator=f"evidence/{stage}.md",
            assignment_id=work["id"],
        )["artifact"]
        artifact_ids.append(artifact["id"])
        service.complete_work(actor=agent, assignment_id=work["id"])
        proposal = service.propose_transition(
            actor=agent,
            rationale=f"Required {stage} evidence is complete and ready for review.",
            evidence_ids=[artifact["id"]],
        )["proposal"]
        if stage == "design":
            service.approve_transition(
                actor=reviewer,
                proposal_id=proposal["id"],
                approval_role="technical_reviewer",
            )
        elif stage == "verification":
            service.approve_transition(
                actor=release_manager,
                proposal_id=proposal["id"],
                approval_role="release_manager",
            )
            service.approve_transition(
                actor=risk_owner,
                proposal_id=proposal["id"],
                approval_role="risk_owner",
            )
        else:
            service.approve_transition(actor=coordinator, proposal_id=proposal["id"])

    state = repository.load()
    verification = repository.verify_audit()
    return {
        "store": str(Path(store)),
        "project_id": state["project"]["id"],
        "project_name": state["project"]["name"],
        "current_stage": state["current_stage"],
        "artifact_count": len(state["artifacts"]),
        "assignment_count": len(state["assignments"]),
        "proposal_count": len(state["transition_proposals"]),
        "event_count": verification["event_count"],
        "audit_valid": verification["valid"],
        "artifact_ids": artifact_ids,
    }
