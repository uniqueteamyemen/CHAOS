#!/usr/bin/env python3
from pathlib import Path
import json, shutil, tempfile
from chaos_governance_kernel.core import validate_manifest, replay, build_graph, load_manifest, write_json
from chaos_governance_kernel.checks import audit_csv
ROOT=Path('/home/ubuntu/CHAOS')
BUNDLE=ROOT/'experiments/governance_mvp_v1/trade_regime_transition_audit'
MAN=BUNDLE/'GOVERNANCE_BUNDLE_MANIFEST_V1.json'
STATE=ROOT/'experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_STATE_PANEL_V1.csv'
EVENTS=ROOT/'experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_EVENTS_V1.csv'

def main():
 results={}
 results['manifest_validate']=validate_manifest(MAN,ROOT)
 results['replay']=replay(MAN,ROOT,False)
 results['graph']=build_graph(MAN,ROOT)
 results['state_audit']=audit_csv(STATE,['reporter_id','year','regime','total'],['reporter_id','year'],'year','annual')
 results['events_audit']=audit_csv(EVENTS,['reporter_id','event_year','regime_t2','regime_t1','regime_t'],['reporter_id','event_year'],'event_year','annual',['regime_t2','regime_t1','regime_t'],['outcome_'])
 with tempfile.TemporaryDirectory(prefix='chaos-governance-test-') as td:
  td=Path(td)
  bad=json.loads(MAN.read_text()); bad['artifacts'][0]['sha256']='0'*64; badman=td/'bad_manifest.json'; badman.write_text(json.dumps(bad))
  results['mutated_hash_rejected']=validate_manifest(badman,ROOT)
  dup=td/'duplicate_events.csv'; shutil.copy2(EVENTS,dup); with_open=dup.open('a',encoding='utf-8'); with_open.write(EVENTS.read_text(encoding='utf-8').splitlines()[1]+'\n'); with_open.close()
  results['duplicate_key_rejected']=audit_csv(dup,['reporter_id','event_year'],['reporter_id','event_year'],'event_year','annual')
  results['target_leakage_rejected']=audit_csv(EVENTS,['reporter_id'],['reporter_id','event_year'],'event_year','annual',['outcome_h2'],['outcome_'])
  results['assertions']={
   'manifest_pass':results['manifest_validate']['status']=='pass',
   'replay_pass':results['replay']['status']=='pass',
   'graph_built':results['graph']['node_count']>0 and results['graph']['edge_count']>0,
   'state_pass':results['state_audit']['status']=='pass',
   'events_pass':results['events_audit']['status']=='pass',
   'mutated_hash_rejected':results['mutated_hash_rejected']['status']=='fail',
   'duplicate_rejected':results['duplicate_key_rejected']['status']=='fail',
   'leakage_rejected':results['target_leakage_rejected']['status']=='fail'}
 results['status']='pass' if all(results['assertions'].values()) else 'fail'
 out=BUNDLE/'GOVERNANCE_KERNEL_MVP_TEST_REPORT_V1.json'; write_json(out,results); print(json.dumps({'status':results['status'],'assertions':results['assertions'],'graph':{'nodes':results['graph']['node_count'],'edges':results['graph']['edge_count']},'replay':results['replay']['status']},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
