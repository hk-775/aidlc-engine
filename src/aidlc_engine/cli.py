"""Command-line interface with stable JSON results."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from aidlc_engine.demo import run_demo
from aidlc_engine.errors import AIDLCEngineError, PersistenceError, ValidationError
from aidlc_engine.models import Actor
from aidlc_engine.persistence import JsonProjectRepository
from aidlc_engine.policy import validate_policy
from aidlc_engine.service import LifecycleService, sha256_digest
from aidlc_engine.values import DeterministicValueProvider, ValueProvider, parse_timestamp


def _actor_from_args(args: argparse.Namespace) -> Actor:
    return Actor(
        actor_id=args.actor_id,
        kind=args.actor_kind,
        roles=tuple(args.role or ()),
    )


def _add_actor_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--actor-id", required=True)
    parser.add_argument("--actor-kind", required=True, choices=("human", "agent"))
    parser.add_argument(
        "--role",
        action="append",
        default=[],
        help="Actor role; repeat for more than one role.",
    )


def _load_json_file(path: str | Path) -> dict[str, Any]:
    try:
        with Path(path).open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise PersistenceError(
            "JSON file could not be read",
            details={"path": str(path), "reason": str(error)},
        ) from error
    if not isinstance(value, dict):
        raise ValidationError("JSON file root must be an object")
    return value


def _provider_from_args(args: argparse.Namespace) -> ValueProvider:
    if args.id_seed is None and args.fixed_time is None:
        return ValueProvider()
    if args.id_seed is None or args.fixed_time is None:
        raise ValidationError("--id-seed and --fixed-time must be supplied together")
    return DeterministicValueProvider(
        seed=args.id_seed,
        base_time=parse_timestamp(args.fixed_time),
    )


def _emit(value: dict[str, Any], *, pretty: bool, stream: Any | None = None) -> None:
    stream = stream or sys.stdout
    json.dump(
        value,
        stream,
        indent=2 if pretty else None,
        sort_keys=True,
        separators=None if pretty else (",", ":"),
    )
    stream.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aidlc-engine",
        description=(
            "Human-governed automation engine for the AI Development Lifecycle."
        ),
    )
    parser.add_argument(
        "--store",
        default=".aidlc-engine",
        help="Local project storage directory.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    parser.add_argument("--id-seed", help="Deterministic identifier seed.")
    parser.add_argument("--fixed-time", help="Deterministic UTC ISO-8601 base time.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize a local project.")
    init_parser.add_argument("--name", required=True)
    init_parser.add_argument("--description", default="")
    init_parser.add_argument("--policy")
    _add_actor_arguments(init_parser)

    subparsers.add_parser("status", help="Return the current project state.")
    subparsers.add_parser("policy", help="Return the active project policy.")
    subparsers.add_parser("verify-audit", help="Verify the complete audit hash chain.")
    subparsers.add_parser("events", help="Return all audit events in sequence.")

    validate_parser = subparsers.add_parser(
        "validate-policy",
        help="Validate a policy file without changing project state.",
    )
    validate_parser.add_argument("--file", required=True)

    propose_work = subparsers.add_parser("propose-work", help="Propose a work assignment.")
    _add_actor_arguments(propose_work)
    propose_work.add_argument("--assignee-id", required=True)
    propose_work.add_argument("--stage", required=True)
    propose_work.add_argument("--summary", required=True)
    propose_work.add_argument("--deliverable", action="append", required=True)

    approve_work = subparsers.add_parser("approve-work", help="Approve proposed work.")
    _add_actor_arguments(approve_work)
    approve_work.add_argument("--assignment-id", required=True)

    complete_work = subparsers.add_parser("complete-work", help="Complete assigned work.")
    _add_actor_arguments(complete_work)
    complete_work.add_argument("--assignment-id", required=True)

    add_artifact = subparsers.add_parser("add-artifact", help="Register evidence metadata.")
    _add_actor_arguments(add_artifact)
    add_artifact.add_argument("--type", required=True, dest="artifact_type")
    add_artifact.add_argument("--title", required=True)
    digest_group = add_artifact.add_mutually_exclusive_group(required=True)
    digest_group.add_argument("--digest")
    digest_group.add_argument("--file")
    add_artifact.add_argument("--locator", default="")
    add_artifact.add_argument("--assignment-id")

    propose_transition = subparsers.add_parser(
        "propose-transition",
        help="Propose the next adjacent lifecycle stage.",
    )
    _add_actor_arguments(propose_transition)
    propose_transition.add_argument("--rationale", required=True)
    propose_transition.add_argument("--evidence", action="append", default=[])

    approve_transition = subparsers.add_parser(
        "approve-transition",
        help="Record an independent human transition approval.",
    )
    _add_actor_arguments(approve_transition)
    approve_transition.add_argument("--proposal-id", required=True)
    approve_transition.add_argument("--approval-role")

    reject_transition = subparsers.add_parser(
        "reject-transition",
        help="Reject a pending transition proposal.",
    )
    _add_actor_arguments(reject_transition)
    reject_transition.add_argument("--proposal-id", required=True)
    reject_transition.add_argument("--reason", required=True)

    accept_risk = subparsers.add_parser(
        "accept-risk",
        help="Record a human risk-owner decision.",
    )
    _add_actor_arguments(accept_risk)
    accept_risk.add_argument("--title", required=True)
    accept_risk.add_argument("--rationale", required=True)

    guard = subparsers.add_parser(
        "guard-operation",
        help="Check whether an actor may request an operation.",
    )
    _add_actor_arguments(guard)
    guard.add_argument("--operation", required=True)

    subparsers.add_parser(
        "demo",
        help="Create and run the deterministic synthetic lifecycle demonstration.",
    )
    return parser


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "validate-policy":
        policy = validate_policy(_load_json_file(args.file))
        return {"ok": True, "valid": True, "schema_version": policy["schema_version"]}
    if args.command == "demo":
        result = run_demo(args.store)
        return {"ok": True, "demo": result}

    provider = _provider_from_args(args)
    repository = JsonProjectRepository(args.store, provider)
    service = LifecycleService(repository)
    if args.command == "init":
        policy = _load_json_file(args.policy) if args.policy else None
        state = service.initialize(
            name=args.name,
            description=args.description,
            creator=_actor_from_args(args),
            policy=policy,
        )
        return {"ok": True, "state": state}
    if args.command == "status":
        return {"ok": True, "state": repository.load()}
    if args.command == "policy":
        return {"ok": True, "policy": repository.load_policy()}
    if args.command == "verify-audit":
        return {"ok": True, "audit": repository.verify_audit()}
    if args.command == "events":
        return {"ok": True, "events": repository.list_events()}

    actor = _actor_from_args(args)
    if args.command == "propose-work":
        result = service.propose_work(
            actor=actor,
            assignee_id=args.assignee_id,
            stage=args.stage,
            summary=args.summary,
            deliverable_types=args.deliverable,
        )
    elif args.command == "approve-work":
        result = service.approve_work(
            actor=actor,
            assignment_id=args.assignment_id,
        )
    elif args.command == "complete-work":
        result = service.complete_work(
            actor=actor,
            assignment_id=args.assignment_id,
        )
    elif args.command == "add-artifact":
        if args.file:
            try:
                content = Path(args.file).read_bytes()
            except OSError as error:
                raise PersistenceError(
                    "artifact file could not be read",
                    details={"path": args.file, "reason": str(error)},
                ) from error
            digest = sha256_digest(content)
            locator = args.locator or Path(args.file).name
        else:
            digest = args.digest
            locator = args.locator
        result = service.register_artifact(
            actor=actor,
            artifact_type=args.artifact_type,
            title=args.title,
            digest=digest,
            locator=locator,
            assignment_id=args.assignment_id,
        )
    elif args.command == "propose-transition":
        result = service.propose_transition(
            actor=actor,
            rationale=args.rationale,
            evidence_ids=args.evidence,
        )
    elif args.command == "approve-transition":
        result = service.approve_transition(
            actor=actor,
            proposal_id=args.proposal_id,
            approval_role=args.approval_role,
        )
    elif args.command == "reject-transition":
        result = service.reject_transition(
            actor=actor,
            proposal_id=args.proposal_id,
            reason=args.reason,
        )
    elif args.command == "accept-risk":
        result = service.record_risk_acceptance(
            actor=actor,
            title=args.title,
            rationale=args.rationale,
        )
    elif args.command == "guard-operation":
        result = service.guard_operation(actor=actor, operation=args.operation)
    else:
        raise ValidationError("unsupported command")
    return {"ok": True, **result}


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = execute(args)
    except AIDLCEngineError as error:
        _emit({"ok": False, "error": error.to_dict()}, pretty=args.pretty, stream=sys.stderr)
        return error.exit_code
    except Exception as error:  # pragma: no cover - defensive CLI boundary
        _emit(
            {
                "ok": False,
                "error": {
                    "code": "internal_error",
                    "message": "an unexpected internal error occurred",
                    "details": {"type": type(error).__name__},
                },
            },
            pretty=args.pretty,
            stream=sys.stderr,
        )
        return 70
    _emit(result, pretty=args.pretty)
    return 0
