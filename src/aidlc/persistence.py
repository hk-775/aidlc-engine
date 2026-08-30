"""Durable local JSON persistence with recovery and audit integrity checks."""

from __future__ import annotations

import copy
import fcntl
import json
import os
import re
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

from aidlc.audit import (
    GENESIS_HASH,
    build_event,
    canonical_bytes,
    digest_json,
    state_digest,
    verify_event,
)
from aidlc.errors import ConflictError, IntegrityError, NotFoundError, PersistenceError
from aidlc.models import Actor, validate_state, validate_text
from aidlc.policy import validate_policy
from aidlc.values import OperationValues, ValueProvider

EVENT_FILENAME_PATTERN = re.compile(r"^(\d{8})-([a-z][a-z0-9_-]{1,63})\.json$")


@dataclass(slots=True)
class MutationResult:
    event_type: str
    payload: dict[str, Any]
    result: dict[str, Any]


Mutation = Callable[
    [dict[str, Any], dict[str, Any], OperationValues],
    MutationResult,
]


class JsonProjectRepository:
    """Stores one project in a directory of JSON files."""

    def __init__(self, root: str | Path, provider: ValueProvider | None = None) -> None:
        self.root = Path(root)
        self.provider = provider or ValueProvider()
        self.state_path = self.root / "state.json"
        self.policy_path = self.root / "policy.json"
        self.audit_dir = self.root / "audit"
        self.lock_path = self.root / ".aidlc.lock"
        self.pending_path = self.root / ".aidlc.pending.json"

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _reject_symlink(path: Path) -> None:
        if path.is_symlink():
            raise PersistenceError(
                "symbolic links are not accepted for control-plane storage",
                code="unsafe_storage_path",
                details={"path": str(path)},
            )

    def _prepare_root(self, *, create: bool) -> None:
        if self.root.exists():
            self._reject_symlink(self.root)
            if not self.root.is_dir():
                raise PersistenceError("project storage path is not a directory")
        elif not create:
            raise NotFoundError(
                "project storage is not initialized",
                details={"path": str(self.root)},
            )
        else:
            self.root.mkdir(parents=True, mode=0o700)
        if create:
            self.audit_dir.mkdir(mode=0o700, exist_ok=True)
        elif not self.audit_dir.is_dir():
            raise NotFoundError(
                "project audit directory is missing",
                details={"path": str(self.audit_dir)},
            )
        self._reject_symlink(self.audit_dir)

    @contextmanager
    def _locked(self, *, create: bool = False) -> Iterator[None]:
        self._prepare_root(create=create)
        self._reject_symlink(self.lock_path)
        with self.lock_path.open("a+b") as lock_file:
            os.chmod(self.lock_path, 0o600)
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _read_json(self, path: Path) -> dict[str, Any]:
        self._reject_symlink(path)
        try:
            with path.open("r", encoding="utf-8") as handle:
                value = json.load(handle)
        except FileNotFoundError as error:
            raise NotFoundError(
                "required project file is missing",
                details={"path": str(path)},
            ) from error
        except (OSError, json.JSONDecodeError) as error:
            raise PersistenceError(
                "project JSON could not be read",
                details={"path": str(path), "reason": str(error)},
            ) from error
        if not isinstance(value, dict):
            raise PersistenceError(
                "project JSON root must be an object",
                details={"path": str(path)},
            )
        return value

    def _atomic_write_json(self, path: Path, value: dict[str, Any]) -> None:
        temporary_name = f".{path.name}.{os.getpid()}.{os.urandom(6).hex()}.tmp"
        temporary_path = path.parent / temporary_name
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(temporary_path, flags, 0o600)
        try:
            data = canonical_bytes(value) + b"\n"
            with os.fdopen(descriptor, "wb", closefd=False) as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.close(descriptor)
            descriptor = -1
            os.replace(temporary_path, path)
            self._fsync_directory(path.parent)
        except OSError as error:
            raise PersistenceError(
                "atomic JSON write failed",
                details={"path": str(path), "reason": str(error)},
            ) from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if temporary_path.exists():
                temporary_path.unlink()

    def _event_path(self, event: dict[str, Any]) -> Path:
        return self.audit_dir / (
            f"{event['sequence']:08d}-{event['event_id']}.json"
        )

    def _append_event(self, event: dict[str, Any]) -> None:
        event_path = self._event_path(event)
        if event_path.exists():
            existing = self._read_json(event_path)
            if existing != event:
                raise IntegrityError(
                    "an audit sequence already exists with different content",
                    details={"sequence": event["sequence"]},
                )
            return
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(event_path, flags, 0o400)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(canonical_bytes(event) + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(event_path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            self._fsync_directory(self.audit_dir)
        except FileExistsError:
            existing = self._read_json(event_path)
            if existing != event:
                raise IntegrityError(
                    "an audit event append conflicted with existing content",
                    details={"sequence": event["sequence"]},
                )
        except OSError as error:
            raise PersistenceError(
                "audit event append failed",
                details={"path": str(event_path), "reason": str(error)},
            ) from error

    def _finish_pending(self) -> None:
        if not self.pending_path.exists():
            return
        pending = self._read_json(self.pending_path)
        if set(pending) != {"event", "state"}:
            raise IntegrityError("pending transaction has an invalid shape")
        event = pending["event"]
        state = pending["state"]
        if not isinstance(event, dict) or not isinstance(state, dict):
            raise IntegrityError("pending transaction content is invalid")
        if self.state_path.exists():
            current_state = self._read_json(self.state_path)
            validate_state(current_state)
            current_count = current_state["audit"]["event_count"]
            if current_count == event.get("sequence"):
                if current_state != state or current_state["audit"]["head_hash"] != event.get(
                    "hash"
                ):
                    raise IntegrityError(
                        "pending transaction conflicts with the current state"
                    )
                self._verify_audit_unlocked(current_state)
                self.pending_path.unlink()
                self._fsync_directory(self.root)
                return
            if current_count + 1 != event.get("sequence"):
                raise IntegrityError(
                    "pending transaction sequence does not follow current state"
                )
            expected_previous = current_state["audit"]["head_hash"]
        else:
            if event.get("sequence") != 1:
                raise IntegrityError("initial pending transaction must be sequence one")
            expected_previous = GENESIS_HASH
        verify_event(event, expected_previous)
        validate_state(state)
        if state["audit"]["head_hash"] != event["hash"]:
            raise IntegrityError("pending state does not reference its audit event")
        if state_digest(state) != event["state_digest"]:
            raise IntegrityError("pending state content does not match its audit event")
        self._append_event(event)
        self._atomic_write_json(self.state_path, state)
        self._verify_audit_unlocked(state)
        self.pending_path.unlink()
        self._fsync_directory(self.root)

    def initialize(
        self,
        *,
        name: str,
        description: str,
        creator: Actor,
        policy: dict[str, Any],
    ) -> dict[str, Any]:
        if creator.kind != "human":
            from aidlc.errors import AuthorizationError

            raise AuthorizationError(
                "only a human can initialize a governed project",
                code="human_initialization_required",
            )
        validated_policy = validate_policy(policy)
        project_name = validate_text(name, "name", maximum=120)
        project_description = validate_text(
            description,
            "description",
            minimum=0,
            maximum=1000,
        )
        with self._locked(create=True):
            self._finish_pending()
            existing_events = self._audit_files()
            if self.state_path.exists() or existing_events:
                raise ConflictError("project storage is already initialized")
            self._atomic_write_json(self.policy_path, validated_policy)
            values = OperationValues(self.provider, 1)
            project_id = values.identifier("project", project_name)
            event_id = values.identifier("event", "project.initialized")
            state = {
                "schema_version": 1,
                "project": {
                    "id": project_id,
                    "name": project_name,
                    "description": project_description,
                    "created_at": values.timestamp,
                    "created_by": creator.actor_id,
                },
                "policy_digest": digest_json(validated_policy),
                "current_stage": "discovery",
                "revision": 0,
                "artifacts": {},
                "assignments": {},
                "transition_proposals": {},
                "risk_decisions": {},
                "audit": {
                    "event_count": 1,
                    "head_hash": GENESIS_HASH,
                },
            }
            event = build_event(
                sequence=1,
                event_id=event_id,
                timestamp=values.timestamp,
                event_type="project.initialized",
                actor=creator.to_dict(),
                project_id=project_id,
                state_revision=0,
                snapshot_digest=state_digest(state),
                payload={
                    "name": project_name,
                    "policy_digest": state["policy_digest"],
                    "stage": "discovery",
                },
                previous_hash=GENESIS_HASH,
            )
            state["audit"]["head_hash"] = event["hash"]
            validate_state(state)
            self._atomic_write_json(
                self.pending_path,
                {"event": event, "state": state},
            )
            self._finish_pending()
            return copy.deepcopy(state)

    def _load_unlocked(self) -> tuple[dict[str, Any], dict[str, Any]]:
        self._finish_pending()
        state = self._read_json(self.state_path)
        policy = self._read_json(self.policy_path)
        validate_state(state)
        validated_policy = validate_policy(policy)
        actual_policy_digest = digest_json(validated_policy)
        if actual_policy_digest != state["policy_digest"]:
            raise IntegrityError(
                "the stored policy does not match the policy bound to project state"
            )
        self._verify_audit_unlocked(state)
        return state, validated_policy

    def load(self) -> dict[str, Any]:
        with self._locked():
            state, _ = self._load_unlocked()
            return copy.deepcopy(state)

    def load_policy(self) -> dict[str, Any]:
        with self._locked():
            _, policy = self._load_unlocked()
            return copy.deepcopy(policy)

    def mutate(self, actor: Actor, mutation: Mutation) -> dict[str, Any]:
        with self._locked():
            state, policy = self._load_unlocked()
            next_state = copy.deepcopy(state)
            sequence = state["audit"]["event_count"] + 1
            values = OperationValues(self.provider, sequence)
            mutation_result = mutation(next_state, policy, values)
            if not isinstance(mutation_result, MutationResult):
                raise PersistenceError("mutation did not return a MutationResult")
            next_state["revision"] = state["revision"] + 1
            event = build_event(
                sequence=sequence,
                event_id=values.identifier("event", mutation_result.event_type),
                timestamp=values.timestamp,
                event_type=mutation_result.event_type,
                actor=actor.to_dict(),
                project_id=state["project"]["id"],
                state_revision=next_state["revision"],
                snapshot_digest=state_digest(next_state),
                payload=mutation_result.payload,
                previous_hash=state["audit"]["head_hash"],
            )
            next_state["audit"] = {
                "event_count": sequence,
                "head_hash": event["hash"],
            }
            validate_state(next_state)
            self._atomic_write_json(
                self.pending_path,
                {"event": event, "state": next_state},
            )
            self._finish_pending()
            return copy.deepcopy(mutation_result.result)

    def _audit_files(self) -> list[Path]:
        files = []
        for path in self.audit_dir.iterdir():
            if path.name.startswith("."):
                continue
            if not path.is_file() or not EVENT_FILENAME_PATTERN.fullmatch(path.name):
                raise IntegrityError(
                    "unexpected content exists in the audit directory",
                    details={"path": str(path)},
                )
            self._reject_symlink(path)
            files.append(path)
        return sorted(files)

    def _verify_audit_unlocked(self, state: dict[str, Any]) -> dict[str, Any]:
        previous_hash = GENESIS_HASH
        final_event: dict[str, Any] | None = None
        files = self._audit_files()
        if len(files) != state["audit"]["event_count"]:
            raise IntegrityError(
                "audit event count does not match project state",
                details={
                    "files": len(files),
                    "state_count": state["audit"]["event_count"],
                },
            )
        for expected_sequence, path in enumerate(files, start=1):
            match = EVENT_FILENAME_PATTERN.fullmatch(path.name)
            assert match is not None
            event = self._read_json(path)
            if int(match.group(1)) != expected_sequence:
                raise IntegrityError(
                    "audit event filenames are not contiguous",
                    details={"expected_sequence": expected_sequence},
                )
            if event.get("sequence") != expected_sequence:
                raise IntegrityError(
                    "audit event sequence does not match its filename",
                    details={"path": str(path)},
                )
            if event.get("event_id") != match.group(2):
                raise IntegrityError(
                    "audit event id does not match its filename",
                    details={"path": str(path)},
                )
            verify_event(event, previous_hash)
            if event["state_revision"] != expected_sequence - 1:
                raise IntegrityError(
                    "audit event state revision is inconsistent with its sequence",
                    details={"sequence": expected_sequence},
                )
            if event["project_id"] != state["project"]["id"]:
                raise IntegrityError("audit event belongs to a different project")
            previous_hash = event["hash"]
            final_event = event
        if state["revision"] != len(files) - 1:
            raise IntegrityError(
                "project state revision is inconsistent with the audit count"
            )
        if previous_hash != state["audit"]["head_hash"]:
            raise IntegrityError("audit head hash does not match project state")
        if (
            final_event is None
            or final_event["state_revision"] != state["revision"]
            or final_event["state_digest"] != state_digest(state)
        ):
            raise IntegrityError("project state content does not match the final audit event")
        return {
            "valid": True,
            "event_count": len(files),
            "head_hash": previous_hash,
        }

    def verify_audit(self) -> dict[str, Any]:
        with self._locked():
            self._finish_pending()
            state = self._read_json(self.state_path)
            validate_state(state)
            return self._verify_audit_unlocked(state)

    def list_events(self) -> list[dict[str, Any]]:
        with self._locked():
            state, _ = self._load_unlocked()
            del state
            return [self._read_json(path) for path in self._audit_files()]
