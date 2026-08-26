from __future__ import annotations

import csv
import hashlib
from pathlib import Path

WORKSPACE = Path('/home/ubuntu/market_intelligence_workspace')
REPO = Path('/home/ubuntu/CHAOS')
OUT = REPO / 'manifests' / 'EXTERNAL_ASSET_MANIFEST.csv'

EXPLICIT = {
    'catalog_first/raw': 'third-party raw archive; size/licensing policy; local immutable archive retained',
    'catalog_first/staged': 'derived/staged source files; too large for GitHub; reproducible from raw archive',
    'structural_engine/node_modules': 'installed dependency tree; reproducible from package lock',
}

def reason_for(path: Path) -> str:
    rel = path.relative_to(WORKSPACE).as_posix()
    for prefix, reason in EXPLICIT.items():
        if rel == prefix or rel.startswith(prefix + '/'):
            return reason
    if path.stat().st_size > 50 * 1024 * 1024:
        return 'over GitHub practical file-size threshold; local copy retained'
    if rel.endswith('_LONG.csv'):
        return 'large derived long-format export; local copy retained'
    return 'excluded by repository policy'

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

paths=[]
for root in [WORKSPACE/'catalog_first/raw', WORKSPACE/'catalog_first/staged', WORKSPACE/'structural_engine/node_modules']:
    if root.exists():
        paths.extend(p for p in root.rglob('*') if p.is_file())
for p in WORKSPACE.rglob('*'):
    if not p.is_file():
        continue
    rel=p.relative_to(WORKSPACE).as_posix()
    if p.stat().st_size > 50 * 1024 * 1024 or rel.endswith('_LONG.csv'):
        paths.append(p)

unique={p.resolve() for p in paths}
rows=[]
for p in sorted(unique, key=lambda x: x.as_posix()):
    rows.append({
      'workspace_relative_path':p.relative_to(WORKSPACE).as_posix(),
      'local_path':str(p),
      'size_bytes':p.stat().st_size,
      'sha256':sha256(p),
      'reason_excluded_from_git':reason_for(p),
      'source_remains_local': 'yes',
    })
OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys()) if rows else ['workspace_relative_path','local_path','size_bytes','sha256','reason_excluded_from_git','source_remains_local'])
    w.writeheader(); w.writerows(rows)
print(f'wrote {OUT} rows={len(rows)} total_bytes={sum(int(r["size_bytes"]) for r in rows)}')
