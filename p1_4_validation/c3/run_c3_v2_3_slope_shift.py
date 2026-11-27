from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import numpy as np
from p1_4_validation.c3 import run_c3_v2_2_equal_risk_evaluation as c3
from p1_4_validation.c3.c3_v2_3_slope_shift_calibration import DETECTORS, _sha256, _canonical_json
from p1_4_validation.c3.c3_v2_3_slope_shift_series import evaluate_series
PROTOCOL_PATH = Path('p1_4_validation/c3/c3_v2_3_slope_shift_preregistration.json')

def run(args):
    protocol_path = Path(args.protocol)
    protocol_bytes = protocol_path.read_bytes()
    protocol = json.loads(protocol_bytes)
    if protocol.get('status') != 'PRE_REGISTERED':
        raise ValueError('C3_V2_3_PROTOCOL_NOT_PREREGISTERED')
    if protocol.get('source', {}).get('source_intake_run_id') != str(args.expected_source_run_id):
        raise ValueError('C3_V2_3_SOURCE_RUN_ID_MISMATCH')
    replicates = int(protocol['null_protocol']['replicates_per_phase'])
    if int(args.replicates) != replicates:
        raise ValueError('BAD_REPLICATE_COUNT')
    source_zip, contract_path = (Path(args.source_zip), Path(args.contract))
    manifest, raw_by_series, contract, archive_sha, contract_sha = c3.verify_source_bundle(source_zip, contract_path)
    if str(manifest.get('workflow_run_id')) != str(args.expected_source_run_id):
        raise ValueError('C3_V2_3_SOURCE_MANIFEST_RUN_ID_MISMATCH')
    if manifest['normalized_tape']['sha256'] != protocol['source']['normalized_tape_sha256']:
        raise ValueError('BAD_TAPE_SHA')
    if contract_sha != protocol['source']['evaluation_contract_sha256']:
        raise ValueError('C3_V2_3_EVALUATION_CONTRACT_SHA256_MISMATCH')
    by_series, transform_audit = c3.apply_causal_series_transforms(source_zip, manifest, raw_by_series, contract)
    analysis_tape_sha = c3.analysis_tape_sha256(by_series)
    min_valid = int(protocol['null_protocol']['minimum_valid_replicates'])
    if min_valid != int(np.ceil(replicates * 0.95)):
        raise ValueError('C3_V2_3_MIN_VALID_REPLICATE_POLICY_MISMATCH')
    if float(protocol['risk_gates']['development_wilson_u95_max']) != 0.085:
        raise ValueError('C3_V2_3_DEV_RISK_GATE_MUTATED')
    if float(protocol['risk_gates']['holdout_wilson_u95_max']) != 0.1:
        raise ValueError('C3_V2_3_HOLDOUT_RISK_GATE_MUTATED')
    series_reports, event_rows, unmatched_all = ({}, [], {})
    expected_series = list(protocol['analysis']['target_series'])
    for series_id in expected_series:
        if series_id not in by_series:
            raise ValueError(f'C3_V2_3_TARGET_SERIES_MISSING:{series_id}')
        series_report, historical, unmatched = evaluate_series(series_id=series_id, rows=by_series[series_id], contract_events=contract['events'], manifest=manifest, protocol=protocol, replicates=replicates, min_valid=min_valid)
        series_reports[series_id] = series_report
        event_rows.extend(historical)
        unmatched_all[series_id] = unmatched
        print('C3_V2_3_SERIES_COMPLETE ' + series_id + ' ' + ' '.join((f"{name}={series_report.get('calibration', {}).get(name, {}).get('risk_validation_status', 'ABSTAINED')}" for name in DETECTORS)), flush=True)
    overall = 'COMPLETED_WITH_SERIES_EXCEPTIONS' if any((series_reports.get(sid, {}).get('status') != 'EVALUATED' for sid in expected_series)) else 'COMPLETED_WITH_DETECTOR_VALIDATION_RESULTS'
    detector_summary = {}
    for detector in DETECTORS:
        matched_rows = [row for row in event_rows if row['detector'] == detector]
        matched = [row for row in matched_rows if row['hit_miss'] == 'HIT']
        episodes = {row['episode_id'] for row in matched}
        unmatched_count = sum((unmatched_all.get(sid, {}).get(detector, {}).get('unmatched_alarm_count', 0) for sid in expected_series))
        validated = sum((series_reports.get(sid, {}).get('calibration', {}).get(detector, {}).get('risk_validation_status') == 'VALIDATED' for sid in expected_series))
        detector_summary[detector] = {'validated_series_count': int(validated), 'series_count': len(expected_series), 'matched_event_series_pairs': len(matched), 'total_event_series_pairs': len(matched_rows), 'matched_episode_clusters': len(episodes), 'total_episode_clusters': len({row['episode_id'] for row in matched_rows}), 'unmatched_alarm_count': int(unmatched_count), 'historical_matching_is_diagnostic': True}
    replay = 'python p1_4_validation/c3/run_c3_v2_3_slope_shift.py --source-zip <repacked-frozen-source-intake.zip> --contract p1_4_validation/c3/c3_expanded_event_cohort_v2_2.json --protocol p1_4_validation/c3/c3_v2_3_slope_shift_preregistration.json --expected-source-run-id 45757611871 --replicates 2000 --output-dir artifacts/p1_4/c3/v2_3_causal_slope_shift'
    return {'schema_version': '1.0.0', 'experiment_id': 'C3_V2_3_CAUSAL_LOCAL_SLOPE_SHIFT_2000X2_V1', 'status': overall, 'run_id': os.environ.get('GITHUB_RUN_ID', 'LOCAL_REPLAY'), 'evaluation_commit': os.environ.get('GITHUB_SHA', 'LOCAL_REPLAY'), 'protocol_sha256': _sha256(protocol_bytes), 'source_integrity': {'source_intake_run_id': manifest.get('workflow_run_id'), 'repacked_source_archive_sha256': archive_sha, 'source_artifact_id': protocol['source']['source_artifact_id'], 'source_artifact_zip_sha256': protocol['source']['source_artifact_zip_sha256'], 'normalized_tape_sha256': manifest['normalized_tape']['sha256'], 'contract_sha256': contract_sha, 'analysis_tape_sha256': analysis_tape_sha, 'analysis_transforms': transform_audit, 'source_archive_mutated': False}, 'protocol': protocol, 'series': series_reports, 'historical_results': event_rows, 'unmatched_alarm_summary': unmatched_all, 'detector_summary': detector_summary, 'replay_command': replay}

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-zip', required=True)
    parser.add_argument('--contract', required=True)
    parser.add_argument('--protocol', default=str(PROTOCOL_PATH))
    parser.add_argument('--expected-source-run-id', required=True)
    parser.add_argument('--replicates', type=int, default=2000)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    report = run(args)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / 'C3_V2_3_SLOPE_SHIFT_EVALUATION.json'
    report_bytes = _canonical_json(report)
    report_path.write_bytes(report_bytes)
    report_sha = _sha256(report_bytes)
    manifest = {'schema_version': '1.0.0', 'run_id': report['run_id'], 'evaluation_commit': report['evaluation_commit'], 'protocol_sha256': report['protocol_sha256'], 'source_intake_run_id': report['source_integrity']['source_intake_run_id'], 'repacked_source_archive_sha256': report['source_integrity']['repacked_source_archive_sha256'], 'source_artifact_id': report['source_integrity']['source_artifact_id'], 'source_artifact_zip_sha256': report['source_integrity']['source_artifact_zip_sha256'], 'normalized_tape_sha256': report['source_integrity']['normalized_tape_sha256'], 'evaluation_contract_sha256': report['source_integrity']['contract_sha256'], 'analysis_tape_sha256': report['source_integrity']['analysis_tape_sha256'], 'report_path': report_path.name, 'report_sha256': report_sha, 'seed_namespace': report['protocol']['null_protocol']['seed_namespace'], 'replay_command': report['replay_command']}
    manifest_path = output / 'C3_V2_3_SLOPE_SHIFT_MANIFEST.json'
    manifest_bytes = _canonical_json(manifest)
    manifest_path.write_bytes(manifest_bytes)
    print(json.dumps({'experiment_id': report['experiment_id'], 'status': report['status'], 'run_id': report['run_id'], 'report': str(report_path), 'report_sha256': report_sha, 'manifest': str(manifest_path), 'manifest_sha256': _sha256(manifest_bytes), 'detector_summary': report['detector_summary']}, ensure_ascii=False, indent=2), flush=True)
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
