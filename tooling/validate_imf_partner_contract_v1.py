#!/usr/bin/env python3
from pathlib import Path
import json
P=Path('/home/ubuntu/CHAOS/experimental_contracts/IMF_IMTS_DOMINANT_PARTNER_DEPENDENCE_CONTRACT_V1.json'); d=json.loads(P.read_text()); errors=[]
def req(path):
 x=d
 for k in path.split('.'):
  if not isinstance(x,dict) or k not in x: errors.append('missing:'+path); return None
  x=x[k]
 return x
for path in ['contract_id','status','source_contract.trade_dataset_urn','source_contract.trade_observation_artifact','analysis_unit.primary_unit','partner_selection.selection_rule','partner_exclusion_policy.excluded_code_register_required','trade_exposure_states.primary_state.formula','target_definition.outcome_formula','chronological_design.confirmation','partner_identity_null.primary_identity_null.procedure','partner_identity_null.primary_identity_null.replicates','additional_null_controls.outcome_null.replicates','governance.research_ledger_append_only']:
 req(path)
assert d['status']=='draft_for_review'; assert d['source_contract']['raw_policy']['imputation'] is False; assert d['source_contract']['raw_policy']['normalization'] is False; assert d['source_contract']['raw_policy']['frequency_conversion'] is False; assert d['partner_selection']['selection_uses_target_gdp'] is False; assert d['partner_selection']['selection_uses_confirmation'] is False; assert d['partner_exclusion_policy']['world_denominator_exception'].startswith('G001'); assert d['partner_identity_null']['primary_identity_null']['preserves'][0]=='reporter identities'; assert d['partner_identity_null']['primary_identity_null']['breaks_only'].startswith('The mapping'); assert d['target_definition']['future_data_usage'].startswith('Future GDP enters only'); assert d['multiple_testing_and_promotion']['causal_claim_allowed'] is False; assert d['governance']['runtime_eligible_without_gate'] is False; assert d['multiple_testing_and_promotion']['positive_composer_weight_allowed_only_after_gate'] is True
if errors: raise SystemExit(';'.join(errors))
print(json.dumps({'status':'pass','contract_id':d['contract_id'],'sections':len(d),'exclusion_rules':len(d['partner_exclusion_policy']['exclude_if_source_name_matches_case_insensitive']),'identity_null_replicates':d['partner_identity_null']['primary_identity_null']['replicates'],'outcome_null_replicates':d['additional_null_controls']['outcome_null']['replicates'],'selection_window':d['native_frequency_and_period']['selection_window'],'fit':d['chronological_design']['fit'],'validation':d['chronological_design']['validation'],'confirmation':d['chronological_design']['confirmation'],'causal_claim':d['multiple_testing_and_promotion']['causal_claim_allowed']},ensure_ascii=False,indent=2))
