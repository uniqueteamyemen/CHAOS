from __future__ import annotations
import json
import os
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path('/tmp/c3-v2-3-source')
OUT = Path('/tmp/c3-v2-3-frozen-source.zip')
EXPECTED = {
    'workflow_run_id': '45757611871',
    'contract_id': 'CHAOS_P1_4_C3_EXPANDED_EVENT_COHORT_V1',
    'status': 'SOURCE_TAPES_ACQUIRED_NOT_DETECTOR_EXECUTED',
    'event_count': 20,
    'series_count': 4,
    'event_series_pair_count': 37,
    'point_count': 2141,
}


def main() -> int:
    manifest_path = ROOT / 'expanded_source_intake_manifest.json'
    tape_path = ROOT / 'expanded_initial_release_tape.csv'
    if not manifest_path.is_file() or not tape_path.is_file():
        raise SystemExit('C3_V2_3_SOURCE_REQUIRED_FILES_MISSING')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for key, expected in EXPECTED.items():
        if str(manifest.get(key)) != str(expected):
            raise SystemExit(f'C3_V2_3_SOURCE_MANIFEST_{key.upper()}_MISMATCH')
    if os.environ.get('SOURCE_INTAKE_RUN_ID') != EXPECTED['workflow_run_id']:
        raise SystemExit('C3_V2_3_SOURCE_ENV_RUN_ID_MISMATCH')
    if manifest.get('normalized_tape', {}).get('sha256') != os.environ.get('SOURCE_TAPE_SHA256'):
        raise SystemExit('C3_V2_3_NORMALIZED_TAPE_SHA256_MISMATCH')
    if len(manifest.get('raw_vintage_batches', [])) != 219:
        raise SystemExit('C3_V2_3_RAW_BATCH_COUNT_MISMATCH')
    required = {'expanded_source_intake_manifest.json', 'expanded_initial_release_tape.csv'}
    for batch in manifest['raw_vintage_batches']:
        name = str(batch['file'])
        safe = PurePosixPath(name)
        if safe.is_absolute() or '..' in safe.parts or name in required:
            raise SystemExit(f'C3_V2_3_RAW_BATCH_PATH_INVALID:{name}')
        member = ROOT.joinpath(*safe.parts)
        if not member.is_file() or not member.resolve().is_relative_to(ROOT.resolve()):
            raise SystemExit(f'C3_V2_3_RAW_BATCH_MISSING_OR_UNSAFE:{name}')
        required.add(name)
    files = sorted(p for p in ROOT.rglob('*') if p.is_file())
    names = {p.relative_to(ROOT).as_posix() for p in files}
    if names != required or len(files) != 221:
        raise SystemExit(f'C3_V2_3_SOURCE_MEMBER_SET_MISMATCH:{len(files)}')
    with zipfile.ZipFile(OUT, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(OUT) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != 221:
            raise SystemExit('C3_V2_3_REPACKED_ARCHIVE_CORRUPT')
    print(f'C3_V2_3_FROZEN_SOURCE_READY run_id={EXPECTED["workflow_run_id"]} points=2141 raw_batches=219 members=221 bytes={OUT.stat().st_size}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
