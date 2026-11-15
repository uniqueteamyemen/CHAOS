"""Durable package-level checkpoints for long-running CHAOS experiments."""
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = 1
PACKAGE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$")

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def relative_path(value: str | Path, root: Path = ROOT) -> str:
    candidate = (root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    try:
        return candidate.relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("checkpoint_path_outside_repository") from exc

def validate_package_id(package_id: str) -> str:
    if not PACKAGE_ID_RE.fullmatch(package_id):
        raise ValueError("checkpoint_package_id_invalid")
    return package_id

def input_manifest(paths: Sequence[str], *, root: Path = ROOT) -> list[dict[str, str]]:
    if not paths:
        raise ValueError("checkpoint_inputs_required")
    entries = {}
    for value in paths:
        relative = relative_path(value, root)
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"checkpoint_input_missing:{relative}")
        entries[relative] = sha256_file(path)
    return [{"path": key, "sha256": entries[key]} for key in sorted(entries)]

def fingerprint_inputs(manifest: Sequence[Mapping[str, str]]) -> str:
    canonical = json.dumps(list(manifest), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()

def checkpoint_path(package_id: str, fingerprint: str, *, root: Path = ROOT) -> Path:
    validate_package_id(package_id)
    if not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
        raise ValueError("checkpoint_fingerprint_invalid")
    return root / "experiments" / "identity_lab" / "checkpoints" / package_id / f"{fingerprint}.json"

def summarize_result(path: Path) -> dict[str, Any]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"summary_status": "unavailable", "reason": type(exc).__name__}
    if not isinstance(report, dict):
        return {"summary_status": "unavailable", "reason": "json_root_not_object"}
    if "decisions" in report and "candidates" in report:
        return {key: report.get(key) for key in (
            "experiment", "source", "source_series", "temporal_split", "decisions", "promotion"
        )}
    if isinstance(report.get("result"), dict):
        result = report["result"]
        summary = {key: result.get(key) for key in (
            "source", "matched_series_count", "matched_ready_periods",
            "null_calibration_matched_series_count", "null_calibration_matched_ready_periods",
            "temporal_split"
        )}
        summary["experiment"] = report.get("experiment")
        calibrations = result.get("stationary_bootstrap_null_calibration", {})
        for name, calibration in calibrations.items():
            detectors = calibration.get("detectors", {}) if isinstance(calibration, dict) else {}
            summary[f"{name}_null"] = {
                "status": calibration.get("status") if isinstance(calibration, dict) else None,
                "series_count": calibration.get("series_count") if isinstance(calibration, dict) else None,
                "passing_settings": {
                    detector: sum(1 for item in values if item.get("passes_all_probabilities"))
                    for detector, values in detectors.items() if isinstance(values, list)
                },
            }
        return summary
    return {"experiment": report.get("experiment"), "source": report.get("source"), "summary_status": "generic"}

def build_checkpoint_record(*, package_id: str, inputs: Sequence[str], tests_status: str,
    experiment_status: str, result_file: str, artifact_id: str = "", artifact_digest: str = "",
    artifact_url: str = "", decision: str = "", root: Path = ROOT,
    environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    env = dict(os.environ if environ is None else environ)
    package_id = validate_package_id(package_id)
    manifest = input_manifest(inputs, root=root)
    fingerprint = fingerprint_inputs(manifest)
    result_rel = relative_path(result_file, root) if result_file else ""
    result_path = root / result_rel if result_rel else None
    result_exists = bool(result_path and result_path.is_file())
    result_hash = sha256_file(result_path) if result_exists and result_path else None
    result_size = result_path.stat().st_size if result_exists and result_path else None
    summary = summarize_result(result_path) if result_exists and result_path else {
        "summary_status": "unavailable", "reason": "result_file_missing"
    }
    reasons = []
    if tests_status != "success": reasons.append("tests_not_success")
    if experiment_status != "success": reasons.append("experiment_not_success")
    if not result_exists: reasons.append("result_file_missing")
    if not artifact_id or not artifact_digest: reasons.append("artifact_not_uploaded_or_missing_digest")
    run_id, repository = env.get("GITHUB_RUN_ID", ""), env.get("GITHUB_REPOSITORY", "")
    run_url = f"{env.get('GITHUB_SERVER_URL', 'https://github.com')}/{repository}/actions/runs/{run_id}" if repository and run_id else ""
    return {
        "schema_version": SCHEMA_VERSION, "package_id": package_id,
        "status": "completed" if not reasons else "incomplete", "status_reasons": reasons,
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input_fingerprint": fingerprint, "inputs": manifest,
        "source_commit": env.get("GITHUB_SHA", ""), "branch": env.get("GITHUB_REF_NAME", ""),
        "workflow": env.get("GITHUB_WORKFLOW", ""), "workflow_run_id": run_id,
        "workflow_run_attempt": env.get("GITHUB_RUN_ATTEMPT", ""), "workflow_run_url": run_url,
        "tests_status": tests_status, "experiment_status": experiment_status, "decision": decision,
        "result": {"path": result_rel, "sha256": result_hash, "bytes": result_size, "summary": summary},
        "artifact": {"id": str(artifact_id), "digest": str(artifact_digest), "url": str(artifact_url)},
        "resume_rule": "Skip only when status=completed and the current declared input fingerprint exactly matches this checkpoint."
    }

def is_resumable(package_id: str, inputs: Sequence[str], *, root: Path = ROOT) -> tuple[bool, str, Path]:
    package_id = validate_package_id(package_id)
    fingerprint = fingerprint_inputs(input_manifest(inputs, root=root))
    path = checkpoint_path(package_id, fingerprint, root=root)
    if not path.is_file(): return False, "no_matching_checkpoint", path
    try: record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError): return False, "checkpoint_unreadable", path
    valid = (record.get("schema_version") == SCHEMA_VERSION
        and record.get("package_id") == package_id
        and record.get("input_fingerprint") == fingerprint
        and record.get("status") == "completed")
    return (True, "completed_checkpoint_matches_inputs", path) if valid else (
        False, "checkpoint_not_complete_or_mismatched", path
    )

def persist_checkpoint(path: Path, *, branch: str, root: Path = ROOT) -> None:
    if not branch or branch.startswith("-") or "/" not in branch:
        raise ValueError("checkpoint_branch_invalid")
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    def git(args: list[str], check: bool = True):
        return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=check)
    git(["config", "user.name", "github-actions[bot]"])
    git(["config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"])
    git(["add", "--", relative])
    staged = git(["diff", "--cached", "--quiet"], check=False)
    if staged.returncode == 0: return
    if staged.returncode != 1: raise RuntimeError("checkpoint_git_staging_failed:" + staged.stderr)
    git(["commit", "-m", f"checkpoint(chaos): record {path.stem[:16]}"])
    remote_ref, last_error = f"refs/remotes/origin/{branch}", ""
    for _ in range(3):
        git(["fetch", "origin", branch])
        rebase = git(["rebase", remote_ref], check=False)
        if rebase.returncode:
            git(["rebase", "--abort"], check=False)
            last_error = rebase.stderr or rebase.stdout
            continue
        push = git(["push", "origin", f"HEAD:refs/heads/{branch}"], check=False)
        if push.returncode == 0: return
        last_error = push.stderr or push.stdout
    raise RuntimeError("checkpoint_git_push_failed:" + last_error)

def emit_github_output(path: str, values: Mapping[str, Any]) -> None:
    if not path: return
    with Path(path).open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            stream.write(f"{key}={str(value).lower() if isinstance(value, bool) else value}\n")

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    resume = commands.add_parser("resume")
    resume.add_argument("--package-id", required=True)
    resume.add_argument("--input", action="append", required=True)
    resume.add_argument("--github-output", default="")
    record = commands.add_parser("record")
    record.add_argument("--package-id", required=True)
    record.add_argument("--input", action="append", required=True)
    record.add_argument("--tests-status", required=True)
    record.add_argument("--experiment-status", required=True)
    record.add_argument("--result-file", required=True)
    record.add_argument("--artifact-id", default="")
    record.add_argument("--artifact-digest", default="")
    record.add_argument("--artifact-url", default="")
    record.add_argument("--decision", default="")
    record.add_argument("--persist", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "resume":
            ok, reason, path = is_resumable(args.package_id, args.input)
            emit_github_output(args.github_output, {"resumable": ok, "resume_reason": reason})
            print(json.dumps({"resumable": ok, "reason": reason, "checkpoint_path": path.relative_to(ROOT).as_posix()}))
            return 0
        record_data = build_checkpoint_record(
            package_id=args.package_id, inputs=args.input, tests_status=args.tests_status,
            experiment_status=args.experiment_status, result_file=args.result_file,
            artifact_id=args.artifact_id, artifact_digest=args.artifact_digest,
            artifact_url=args.artifact_url, decision=args.decision,
        )
        path = checkpoint_path(record_data["package_id"], record_data["input_fingerprint"])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(record_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
        if args.persist: persist_checkpoint(path, branch=os.environ.get("GITHUB_REF_NAME", ""))
        print(json.dumps({"checkpoint_path": path.relative_to(ROOT).as_posix(),
            "status": record_data["status"], "status_reasons": record_data["status_reasons"],
            "input_fingerprint": record_data["input_fingerprint"], "result_sha256": record_data["result"]["sha256"]}))
        return 0
    except Exception as exc:
        print(f"checkpoint_error:{type(exc).__name__}:{exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
