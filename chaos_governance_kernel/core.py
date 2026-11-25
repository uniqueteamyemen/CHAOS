from __future__ import annotations
import hashlib, json, os, shlex, subprocess, sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def canonical_sha256(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class Artifact:
    path: str
    role: str
    sha256: str
    bytes: int


def registry_entry(path: Path, source_root: Path, role: str) -> Artifact:
    if not path.is_file():
        raise FileNotFoundError(path)
    rel = path.resolve().relative_to(source_root.resolve()).as_posix()
    return Artifact(path=rel, role=role, sha256=sha256_file(path), bytes=path.stat().st_size)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n')


RESEARCH_LEDGER_REQUIRED_FIELDS = {
    "ledger_id", "record_type", "created_at_utc", "source_refs",
    "contract_ref", "input_hashes", "output_refs", "status", "notes",
}
RESEARCH_LEDGER_RECORD_TYPES = {
    "source", "contract", "run", "domain_state", "transition_evidence",
    "pattern_decision", "runtime_alert", "qa",
}


def append_research_ledger_record(path: Path, record: dict[str, Any]) -> dict[str, Any]:
    """Append one validated, idempotent record to the canonical research ledger.

    A sidecar advisory lock serializes writers across processes. A repeated
    ledger_id with identical content is a no-op; a repeated ID with different
    content is a hard integrity error. Corrupt existing JSONL fails closed.
    """
    if not isinstance(record, dict):
        raise ValueError("research_ledger_record_must_be_object")
    missing = sorted(RESEARCH_LEDGER_REQUIRED_FIELDS - set(record))
    if missing:
        raise ValueError("research_ledger_fields_missing:" + ",".join(missing))
    if record.get("record_type") not in RESEARCH_LEDGER_RECORD_TYPES:
        raise ValueError("research_ledger_record_type_invalid")
    ledger_id = record.get("ledger_id")
    if not isinstance(ledger_id, str) or not ledger_id.startswith("ledger:v1:sha256:"):
        raise ValueError("research_ledger_id_invalid")
    payload = {key: value for key, value in record.items() if key != "ledger_id"}
    expected_id = "ledger:v1:sha256:" + canonical_sha256(payload)
    if ledger_id != expected_id:
        raise ValueError("research_ledger_id_content_mismatch")
    try:
        rendered = json.dumps(
            record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("research_ledger_record_not_canonical_json") from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with lock_path.open("a+b") as lock_handle:
        if os.name == "nt":
            import msvcrt
            if lock_path.stat().st_size == 0:
                lock_handle.write(b"0")
                lock_handle.flush()
            lock_handle.seek(0)
            msvcrt.locking(lock_handle.fileno(), msvcrt.LK_LOCK, 1)
            unlock = lambda: (lock_handle.seek(0), msvcrt.locking(lock_handle.fileno(), msvcrt.LK_UNLCK, 1))
        else:
            import fcntl
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            unlock = lambda: fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
        try:
            if path.exists():
                with path.open("r", encoding="utf-8") as existing:
                    for line_number, line in enumerate(existing, 1):
                        if not line.strip():
                            continue
                        try:
                            previous = json.loads(line)
                        except json.JSONDecodeError as exc:
                            raise ValueError(f"research_ledger_jsonl_corrupt:line={line_number}") from exc
                        if previous.get("ledger_id") == ledger_id:
                            if previous == record:
                                return {
                                    "status": "already_recorded",
                                    "ledger_id": ledger_id,
                                    "path": str(path),
                                }
                            raise ValueError("research_ledger_duplicate_id_content_conflict")
            with path.open("a", encoding="utf-8", newline="\n") as output:
                output.write(rendered + "\n")
                output.flush()
                os.fsync(output.fileno())
        finally:
            unlock()
    return {"status": "appended", "ledger_id": ledger_id, "path": str(path)}


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or 'artifacts' not in data:
        raise ValueError('manifest must be an object with artifacts')
    if not isinstance(data['artifacts'], list):
        raise ValueError('manifest.artifacts must be a list')
    return data


def validate_manifest(manifest_path: Path, source_root: Path) -> dict[str, Any]:
    m = load_manifest(manifest_path)
    seen = set(); results=[]; failures=[]
    for item in m['artifacts']:
        rel = item['path']
        if rel in seen:
            failures.append({'path': rel, 'reason': 'duplicate_path'})
            continue
        seen.add(rel)
        p = source_root / rel
        if not p.is_file():
            failures.append({'path': rel, 'reason': 'missing'})
            continue
        actual_sha = sha256_file(p); actual_bytes = p.stat().st_size
        ok = actual_sha == item.get('sha256') and actual_bytes == item.get('bytes')
        results.append({'path': rel, 'expected_sha256': item.get('sha256'), 'actual_sha256': actual_sha, 'expected_bytes': item.get('bytes'), 'actual_bytes': actual_bytes, 'ok': ok})
        if not ok:
            failures.append({'path': rel, 'reason': 'hash_or_size_mismatch'})
    status = 'pass' if not failures else 'fail'
    return {'manifest': str(manifest_path), 'artifact_count': len(m['artifacts']), 'checked_count': len(results), 'failures': failures, 'status': status, 'checked_at': utc_now()}


def replay(manifest_path: Path, source_root: Path, check_only: bool = False) -> dict[str, Any]:
    m = load_manifest(manifest_path)
    command = m.get('replay', {}).get('command')
    cwd_rel = m.get('replay', {}).get('cwd', '.')
    outputs = m.get('replay', {}).get('outputs', [])
    if not command:
        raise ValueError('manifest.replay.command is required')
    before = validate_manifest(manifest_path, source_root)
    if before['status'] != 'pass':
        return {'status': 'blocked', 'reason': 'input_manifest_validation_failed', 'validation': before}
    if check_only:
        return {'status': 'ready', 'command': command, 'outputs': outputs}
    proc = subprocess.run(command, cwd=str(source_root / cwd_rel), capture_output=True, text=True, check=False)
    out = {'status': 'pass' if proc.returncode == 0 else 'fail', 'returncode': proc.returncode, 'command': command, 'stdout': proc.stdout, 'stderr': proc.stderr, 'outputs': []}
    for item in outputs:
        p = source_root / item['path']
        if not p.is_file():
            out['status']='fail'; out['outputs'].append({'path':item['path'],'ok':False,'reason':'missing_output'}); continue
        actual=sha256_file(p); ok=actual==item['sha256']; out['outputs'].append({'path':item['path'],'expected_sha256':item['sha256'],'actual_sha256':actual,'ok':ok})
        if not ok: out['status']='fail'
    return out


def build_graph(manifest_path: Path, source_root: Path) -> dict[str, Any]:
    m=load_manifest(manifest_path); bundle=m.get('bundle_id', manifest_path.stem)
    nodes=[{'id':bundle,'type':'governance_bundle','status':m.get('decision_status','unresolved')}]
    edges=[]
    for a in m['artifacts']:
        aid=f"artifact:{a['path']}"; nodes.append({'id':aid,'type':a.get('role','artifact'),'sha256':a.get('sha256'),'bytes':a.get('bytes')}); edges.append({'source':aid,'target':bundle,'relation':'is_registered_in'})
    if m.get('replay'):
        rid=f"replay:{bundle}"; nodes.append({'id':rid,'type':'replay_run','status':'declared'}); edges.append({'source':bundle,'target':rid,'relation':'has_replay'})
        for o in m['replay'].get('outputs',[]): edges.append({'source':rid,'target':f"artifact:{o['path']}",'relation':'produces'})
    if m.get('decision'):
        did=f"decision:{bundle}"; nodes.append({'id':did,'type':'decision','status':m['decision'].get('status')}); edges.append({'source':bundle,'target':did,'relation':'supports_decision'})
    return {'graph_id':f"graph:{bundle}",'generated_at':utc_now(),'nodes':nodes,'edges':edges,'node_count':len(nodes),'edge_count':len(edges)}
