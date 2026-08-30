from __future__ import annotations

import json
from pathlib import Path

from aidlc_engine.audit import validate_event
from aidlc_engine.demo import run_demo
from aidlc_engine.models import HARD_DENIED_AGENT_OPERATIONS, STAGES, validate_state
from aidlc_engine.policy import validate_policy
from aidlc_engine.persistence import JsonProjectRepository
from tests.support import ROOT, WorkspaceTestCase


class SchemaAndFixtureTests(WorkspaceTestCase):
    def load_schema(self, name: str) -> dict[str, object]:
        path = ROOT / "schemas" / name
        return json.loads(path.read_text(encoding="utf-8"))

    def test_all_schema_documents_are_valid_json_objects(self) -> None:
        for name in (
            "policy.schema.json",
            "project-state.schema.json",
            "audit-event.schema.json",
        ):
            with self.subTest(name=name):
                schema = self.load_schema(name)
                self.assertEqual(schema["type"], "object")
                self.assertTrue(str(schema["$id"]).startswith("urn:aidlc-engine:"))

    def test_schema_references_are_local_fragments(self) -> None:
        for path in sorted((ROOT / "schemas").glob("*.json")):
            value = json.loads(path.read_text(encoding="utf-8"))
            serialized = json.dumps(value)
            references = []

            def collect(node: object) -> None:
                if isinstance(node, dict):
                    for key, item in node.items():
                        if key == "$ref":
                            references.append(item)
                        collect(item)
                elif isinstance(node, list):
                    for item in node:
                        collect(item)

            collect(value)
            self.assertTrue(all(str(reference).startswith("#/") for reference in references))
            self.assertNotIn('"$ref": "http', serialized)

    def test_strict_policy_fixture_passes_runtime_validation(self) -> None:
        fixture = json.loads(
            (ROOT / "examples" / "policy.strict.json").read_text(encoding="utf-8")
        )
        validated = validate_policy(fixture)
        self.assertEqual(validated["schema_version"], 1)

    def test_policy_schema_marks_hard_denials_as_false(self) -> None:
        schema = self.load_schema("policy.schema.json")
        properties = schema["properties"]["agent_permissions"]["properties"]
        for operation in HARD_DENIED_AGENT_OPERATIONS:
            with self.subTest(operation=operation):
                self.assertIs(properties[operation]["const"], False)

    def test_state_schema_stage_enum_matches_runtime(self) -> None:
        schema = self.load_schema("project-state.schema.json")
        stage_enum = schema["properties"]["current_stage"]["enum"]
        self.assertEqual(stage_enum, list(STAGES))

    def test_generated_demo_state_passes_runtime_validation(self) -> None:
        store = self.workspace / "demo"
        run_demo(store)
        state = JsonProjectRepository(store).load()
        validate_state(state)
        self.assertEqual(state["current_stage"], "release")

    def test_generated_events_pass_runtime_validation(self) -> None:
        store = self.workspace / "demo"
        run_demo(store)
        events = JsonProjectRepository(store).list_events()
        for event in events:
            validate_event(event)
        self.assertEqual(len(events), 32)

    def test_audit_schema_requires_state_digest(self) -> None:
        schema = self.load_schema("audit-event.schema.json")
        self.assertIn("state_digest", schema["required"])
        self.assertEqual(
            schema["properties"]["state_digest"]["$ref"],
            "#/$defs/hash",
        )

    def test_nested_state_and_actor_schemas_reject_extra_fields(self) -> None:
        state_schema = self.load_schema("project-state.schema.json")
        for name in ("artifact", "assignment", "proposal", "riskDecision", "approval"):
            with self.subTest(name=name):
                self.assertIs(state_schema["$defs"][name]["additionalProperties"], False)

        audit_schema = self.load_schema("audit-event.schema.json")
        actor = audit_schema["properties"]["actor"]
        self.assertIs(actor["additionalProperties"], False)
        self.assertEqual(actor["properties"]["roles"]["maxItems"], 20)

    def test_evidence_fixtures_are_synthetic_markdown(self) -> None:
        fixtures = sorted((ROOT / "examples" / "evidence").glob("*.md"))
        self.assertGreaterEqual(len(fixtures), 2)
        for fixture in fixtures:
            with self.subTest(fixture=fixture.name):
                text = fixture.read_text(encoding="utf-8")
                self.assertIn("Synthetic", text)
                self.assertTrue(text.endswith("\n"))
