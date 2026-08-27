#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json, hashlib
ROOT=Path('/home/ubuntu/CHAOS')
TRANS=ROOT/'experiments/macro_plus_eia_energy/transition_evidence_v1/TRANSITION_EVIDENCE_V1.jsonl'
REG=ROOT/'experiments/macro_plus_eia_energy/CONTROLLED_PATTERN_REGISTRY_V1.jsonl'
NATIVE=ROOT/'experiments/multi_domain_native_adapters_v1/TRANSITION_EVIDENCE_NATIVE_DOMAINS_V1.jsonl'
CROSS=ROOT/'experiments/multi_domain_native_edges_v1/TRANSITION_EVIDENCE_ECONOMIC_TO_CONFLICT_V1.jsonl'
TRADE=ROOT/'campaigns/agents/trade_v1/TRADE_TRANSITION_EVIDENCE_V1.jsonl'
WDI_TRADE=ROOT/'campaigns/agents/trade_v1/WDI_TRADE_TRANSITION_EVIDENCE_V1.jsonl'
TRADE_ECON=ROOT/'campaigns/agents/trade_v1/WDI_TRADE_TO_ECONOMIC_DETERIORATION_TRANSITION_EVIDENCE_V1.jsonl'
WGI=ROOT/'campaigns/agents/institutions_policy_v1/WGI_TRANSITION_EVIDENCE_V1.jsonl'
PMR=ROOT/'campaigns/research_rounds/20260827_BROWSER_DEEP_RESEARCH/OECD_PMR_TRANSITION_EVIDENCE_V1.jsonl'; PMR_SENS=ROOT/'experiments/multi_domain_native_edges_v1/pmr_within_domain_v1/PMR_WITHIN_DOMAIN_TRANSITION_EVIDENCE_V1_1.jsonl'; IMF_IMTS=ROOT/'experiments/multi_domain_native_edges_v1/imf_imts_export_to_gdp_v1/IMF_IMTS_EXPORT_TO_GDP_TRANSITION_EVIDENCE_V1.jsonl'; IMF_PARTNER=ROOT/'experiments/multi_domain_native_edges_v1/imf_partner_dependence_v1/IMF_IMTS_PARTNER_DEPENDENCE_TRANSITION_EVIDENCE_V1.jsonl'; IMF_PARTNER_V2=ROOT/'experiments/multi_domain_native_edges_v2/imf_partner_dependence_v2/IMF_IMTS_PARTNER_DEPENDENCE_TRANSITION_EVIDENCE_V2.jsonl'; IMF_SUBSTITUTION_V3=ROOT/'experiments/dual_track_v02/imf_partner_substitution_v3/IMF_IMTS_PARTNER_SUBSTITUTION_TRANSITION_EVIDENCE_V3.jsonl'; IMF_SUBSTITUTION_V3_1=ROOT/'experiments/dual_track_v02/imf_partner_substitution_v3_1/IMF_IMTS_PARTNER_SUBSTITUTION_V3_1_TRANSITION_EVIDENCE.jsonl'; TRADE_PATH_V1_1=ROOT/'experiments/dual_track_v02/trade_network_adaptation_path_v1_1/TRADE_NETWORK_ADAPTATION_PATH_TRANSITION_EVIDENCE_V1_1.jsonl'; TRADE_REGIME_V1=ROOT/'experiments/dual_track_v02/trade_regime_transition_discovery_v1/TRADE_REGIME_TRANSITION_TRANSITION_EVIDENCE_V1.jsonl'
OUT=ROOT/'experiments/macro_plus_eia_energy/evidence_graph_v1'; OUT.mkdir(parents=True,exist_ok=True)
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 nodes={}; edges=[]
 for line in TRANS.read_text().splitlines():
  if not line.strip():continue
  r=json.loads(line); a=r['source_state']; b=r['target_state']; nodes.setdefault(a,{'node_id':a});nodes.setdefault(b,{'node_id':b}); edges.append({'edge_id':r['transition_id']+'_'+r['split'],'source':a,'target':b,'lag':r.get('lag'),'split':r.get('split'),'metric':r.get('metric'),'p_value':r.get('p_value'),'null_method':r.get('null_method'),'status':r.get('edge_status'),'causal_claim':r.get('causal_claim',False),'source_refs':r.get('source_refs',[]),'failure_cases':r.get('failure_cases',[])})
 for line in REG.read_text().splitlines():
  if not line.strip():continue
  r=json.loads(line); pid=r['pattern_id']; nodes.setdefault(pid,{'node_id':pid,'type':'pattern_record'}); e={'edge_id':pid+'_registry','source':pid,'target':r.get('outcome_family',r.get('statement','unspecified')),'split':'registry','metric':None,'p_value':r.get('evidence',{}).get('maxstat_p_value') if isinstance(r.get('evidence'),dict) else None,'null_method':'registry_summary','status':r.get('status'),'causal_claim':r.get('causal_claim',False),'source_refs':r.get('evidence',{}).get('artifact') if isinstance(r.get('evidence'),dict) else None,'failure_cases':[r.get('interpretation','')]}; edges.append(e)
 for line in NATIVE.read_text().splitlines():
  if not line.strip():continue
  r=json.loads(line); a=r['source_state']; b=r['target_state']; nodes.setdefault(a,{'node_id':a}); nodes.setdefault(b,{'node_id':b}); edges.append({'edge_id':r['transition_id'],'source':a,'target':b,'lag':r.get('lag'),'split':r.get('split'),'metric':r.get('metric'),'p_value':r.get('p_value'),'null_method':r.get('null_method'),'status':r.get('edge_status'),'causal_claim':r.get('causal_claim',False),'source_refs':r.get('source_refs',[]),'failure_cases':r.get('failure_cases',[])})
 for line in CROSS.read_text().splitlines():
  if not line.strip():continue
  r=json.loads(line); a=r['source_state']; b=r['target_state']; nodes.setdefault(a,{'node_id':a}); nodes.setdefault(b,{'node_id':b}); edges.append({'edge_id':r['transition_id'],'source':a,'target':b,'lag':r.get('lag'),'split':r.get('split'),'metric':r.get('metric'),'p_value':r.get('p_value'),'null_method':r.get('null_method'),'status':r.get('edge_status'),'causal_claim':r.get('causal_claim',False),'source_refs':r.get('source_refs',[]),'failure_cases':r.get('failure_cases',[])})
 for source_file in (TRADE,WDI_TRADE,TRADE_ECON,WGI,PMR,PMR_SENS,IMF_IMTS,IMF_PARTNER,IMF_PARTNER_V2,IMF_SUBSTITUTION_V3,IMF_SUBSTITUTION_V3_1,TRADE_PATH_V1_1,TRADE_REGIME_V1):
  for line in source_file.read_text().splitlines():
   if not line.strip():continue
   r=json.loads(line); a=r['source_state']; b=r['target_state']; nodes.setdefault(a,{'node_id':a}); nodes.setdefault(b,{'node_id':b}); edges.append({'edge_id':r['transition_id'],'source':a,'target':b,'lag':r.get('lag'),'split':r.get('split'),'metric':r.get('metric'),'p_value':r.get('p_value'),'null_method':r.get('null_method'),'status':r.get('edge_status'),'causal_claim':r.get('causal_claim',False),'source_refs':r.get('source_refs',[]),'failure_cases':r.get('failure_cases',[])})
 graph={'graph_id':'CHAOS_EVIDENCE_GRAPH_V1','nodes':list(nodes.values()),'edges':edges,'rules':{'positive_composer_input_statuses':['supported_predictive'],'excluded_statuses':['rejected','rejected_by_current_maxstat_null','not_supported_by_current_cross_domain_null','weak_or_unresolved_cross_domain_signal','unresolved','not_testable'],'causal_claims_permitted':False,'native_frequency_preserved':True},'input_hashes':{'transition_evidence':h(TRANS),'registry':h(REG),'native_domain_transition_evidence':h(NATIVE),'cross_domain_transition_evidence':h(CROSS),'trade_transition_evidence':h(TRADE),'wgi_transition_evidence':h(WGI),'wdi_trade_transition_evidence':h(WDI_TRADE),'trade_to_economic_transition_evidence':h(TRADE_ECON),'pmr_transition_evidence':h(PMR),'pmr_sensitivity_transition_evidence':h(PMR_SENS),'imf_imts_export_to_gdp_transition_evidence':h(IMF_IMTS),'imf_partner_dependence_transition_evidence':h(IMF_PARTNER),'imf_partner_dependence_v2_transition_evidence':h(IMF_PARTNER_V2),'imf_partner_substitution_v3_transition_evidence':h(IMF_SUBSTITUTION_V3),'imf_partner_substitution_v3_1_transition_evidence':h(IMF_SUBSTITUTION_V3_1),'trade_network_adaptation_path_v1_1_transition_evidence':h(TRADE_PATH_V1_1),'trade_regime_transition_discovery_v1_transition_evidence':h(TRADE_REGIME_V1)}}
 (OUT/'EVIDENCE_GRAPH_V1.json').write_text(json.dumps(graph,ensure_ascii=False,indent=2)+'\n')
 summary={'graph_id':graph['graph_id'],'node_count':len(graph['nodes']),'edge_count':len(graph['edges']),'edge_status_counts':{},'positive_composer_edges':0,'causal_claims':0}
 for e in edges:
  summary['edge_status_counts'][e['status']]=summary['edge_status_counts'].get(e['status'],0)+1
  if e['status'] in graph['rules']['positive_composer_input_statuses']:summary['positive_composer_edges']+=1
  if e['causal_claim']:summary['causal_claims']+=1
 (OUT/'EVIDENCE_GRAPH_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
