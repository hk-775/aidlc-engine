from __future__ import annotations

import copy
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aidlc_engine.models import Actor
from aidlc_engine.persistence import JsonProjectRepository
from aidlc_engine.policy import default_policy
from aidlc_engine.service import LifecycleService, sha256_digest
from aidlc_engine.values import DeterministicValueProvider

ROOT = Path(__file__).resolve().parents[1]
TEST_TEMP_ROOT = ROOT / ".tmp" / "tests"


class WorkspaceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        TEST_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.temporary_directory = tempfile.TemporaryDirectory(
            prefix=f"{self.__class__.__name__}-",
            dir=TEST_TEMP_ROOT,
        )
        self.workspace = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def create_project(
        self,
        *,
        path: Path | None = None,
        policy: dict[str, Any] | None = None,
        seed: str = "test-seed",
        creator: Actor | None = None,
    ) -> tuple[JsonProjectRepository, LifecycleService]:
        provider = DeterministicValueProvider(
            seed=seed,
            base_time=datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc),
        )
        repository = JsonProjectRepository(path or self.workspace / "project", provider)
        service = LifecycleService(repository)
        service.initialize(
            name="Synthetic delivery project",
            description="Standard test fixture with no external data.",
            creator=creator or Actor("human_owner", "human", ("project_owner",)),
            policy=copy.deepcopy(policy or default_policy()),
        )
        return repository, service


class GovernedProjectTestCase(WorkspaceTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.owner = Actor("human_owner", "human", ("project_owner",))
        self.reviewer = Actor(
            "human_reviewer",
            "human",
            ("technical_reviewer",),
        )
        self.release_manager = Actor(
            "human_release_manager",
            "human",
            ("release_manager",),
        )
        self.risk_owner = Actor("human_risk_owner", "human", ("risk_owner",))
        self.agent = Actor("agent_builder", "agent")
        self.other_agent = Actor("agent_tester", "agent")
        self.repository, self.service = self.create_project(creator=self.owner)

    def fulfill_current_stage(
        self,
        *,
        agent: Actor | None = None,
        artifact_type: str | None = None,
        extra_deliverables: list[str] | None = None,
    ) -> dict[str, Any]:
        agent = agent or self.agent
        state = self.repository.load()
        stage = state["current_stage"]
        policy = self.repository.load_policy()
        selected_type = artifact_type or policy["required_artifacts"][stage][0]
        deliverables = [selected_type, *(extra_deliverables or [])]
        assignment = self.service.propose_work(
            actor=agent,
            assignee_id=agent.actor_id,
            stage=stage,
            summary=f"Prepare {stage} evidence",
            deliverable_types=deliverables,
        )["assignment"]
        self.service.approve_work(actor=self.owner, assignment_id=assignment["id"])
        artifact = self.service.register_artifact(
            actor=agent,
            artifact_type=selected_type,
            title=f"{stage.title()} evidence",
            digest=sha256_digest(f"{stage}:{selected_type}".encode()),
            locator=f"evidence/{stage}-{selected_type}.md",
            assignment_id=assignment["id"],
        )["artifact"]
        if not extra_deliverables:
            self.service.complete_work(actor=agent, assignment_id=assignment["id"])
        return {
            "assignment": assignment,
            "artifact": artifact,
        }

    def propose_current_transition(
        self,
        *,
        proposer: Actor | None = None,
        evidence_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        proposer = proposer or self.agent
        if evidence_ids is None:
            fulfilled = self.fulfill_current_stage(agent=proposer)
            evidence_ids = [fulfilled["artifact"]["id"]]
        return self.service.propose_transition(
            actor=proposer,
            rationale="Required evidence is complete and ready for review.",
            evidence_ids=evidence_ids,
        )["proposal"]

    def approve_proposal_for_stage(self, proposal: dict[str, Any]) -> None:
        source = proposal["source_stage"]
        if source == "design":
            self.service.approve_transition(
                actor=self.reviewer,
                proposal_id=proposal["id"],
                approval_role="technical_reviewer",
            )
        elif source == "verification":
            self.service.approve_transition(
                actor=self.release_manager,
                proposal_id=proposal["id"],
                approval_role="release_manager",
            )
            self.service.approve_transition(
                actor=self.risk_owner,
                proposal_id=proposal["id"],
                approval_role="risk_owner",
            )
        else:
            self.service.approve_transition(
                actor=self.owner,
                proposal_id=proposal["id"],
            )

    def advance_once(self) -> None:
        proposal = self.propose_current_transition()
        self.approve_proposal_for_stage(proposal)

    def advance_to(self, target_stage: str) -> None:
        while self.repository.load()["current_stage"] != target_stage:
            self.advance_once()
