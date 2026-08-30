from __future__ import annotations

from datetime import datetime, timezone

from aidlc.audit import canonical_bytes
from aidlc.models import Actor
from aidlc.persistence import JsonProjectRepository
from aidlc.service import LifecycleService
from aidlc.values import DeterministicValueProvider, ValueProvider
from tests.support import WorkspaceTestCase


class DeterminismTests(WorkspaceTestCase):
    def test_same_inputs_produce_identical_state_and_events(self) -> None:
        first_repository, first_service = self.create_project(
            path=self.workspace / "first",
            seed="repeatable",
        )
        second_repository, second_service = self.create_project(
            path=self.workspace / "second",
            seed="repeatable",
        )
        actor = Actor("human_risk_owner", "human", ("risk_owner",))
        for service in (first_service, second_service):
            service.record_risk_acceptance(
                actor=actor,
                title="Synthetic risk",
                rationale="Same deterministic input.",
            )
        self.assertEqual(first_repository.load(), second_repository.load())
        self.assertEqual(
            first_repository.list_events(),
            second_repository.list_events(),
        )

    def test_different_seed_changes_identifiers(self) -> None:
        first, _ = self.create_project(path=self.workspace / "first", seed="one")
        second, _ = self.create_project(path=self.workspace / "second", seed="two")
        self.assertNotEqual(
            first.load()["project"]["id"],
            second.load()["project"]["id"],
        )

    def test_deterministic_timestamps_follow_event_sequence(self) -> None:
        repository, service = self.create_project(path=self.workspace / "time")
        service.record_risk_acceptance(
            actor=Actor("human_risk_owner", "human", ("risk_owner",)),
            title="Time sequence",
            rationale="Create a second event.",
        )
        events = repository.list_events()
        first = datetime.fromisoformat(events[0]["timestamp"].replace("Z", "+00:00"))
        second = datetime.fromisoformat(events[1]["timestamp"].replace("Z", "+00:00"))
        self.assertEqual((second - first).total_seconds(), 0.000001)

    def test_system_provider_identifiers_are_unique(self) -> None:
        provider = ValueProvider()
        first = provider.identifier("artifact", 1, "same")
        second = provider.identifier("artifact", 1, "same")
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("artifact_"))

    def test_deterministic_provider_normalizes_timezone(self) -> None:
        provider = DeterministicValueProvider(
            "timezone",
            datetime(2026, 2, 1, 5, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(provider.timestamp(1), "2026-02-01T05:00:00.000000Z")

    def test_canonical_json_ignores_dictionary_insertion_order(self) -> None:
        self.assertEqual(
            canonical_bytes({"b": 2, "a": 1}),
            canonical_bytes({"a": 1, "b": 2}),
        )
