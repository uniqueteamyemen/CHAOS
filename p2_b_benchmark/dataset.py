from __future__ import annotations
import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path
from real_data_stress_pipeline import run_pipeline as source
from real_data_stress_pipeline.production_pipeline import candidate_sha256

RUN_SHA = "72edc44b183e0c7c92e1edae362426d189e0c886"
ARTIFACT_SHA = "c83f6e960296fbbdb687650a798959f08cb8d98db68de8ca713d7be278e824fe"
PINK_SHA = "3c8d9d8dbb48342fdbf24777c39a8ce8964cc2fd0958f72f6779e6e4ad99cde2"

def _load_registry(archive: zipfile.ZipFile):
    registry_bytes=archive.read("artifacts/real_data_stress/frozen_candidates.json")
    state_bytes=archive.read("real_data_stress_pipeline/results/prepare_state.json")
    registry_doc=json.loads(registry_bytes); state=json.loads(state_bytes)
    if hashlib.sha256(registry_bytes).hexdigest()!=state["candidate_registry_sha256"]: raise ValueError("candidate_registry_sha256_mismatch")
    if state.get("repository_commit")!=RUN_SHA or state.get("expected_series_count")!=519: raise ValueError("pinned_prepare_identity_mismatch")
    if state.get("pink_count")!=51: raise ValueError("pinned_pink_count_mismatch")
    registry=registry_doc.get("candidates",[])
    if len(registry)!=519: raise ValueError("candidate_registry_count_mismatch")
    return state,registry,{row["id"]:row for row in registry}

def _load_gem(archive:zipfile.ZipFile,state:dict,registry_by_id:dict):
    items=[]
    for shard in range(int(state["shard_count"])):
        name=f"artifacts/real_data_stress/candidate_shards/shard-{shard}.json"
        raw=archive.read(name)
        if hashlib.sha256(raw).hexdigest()!=state["shard_payload_sha256"][str(shard)]: raise ValueError(f"candidate_shard_sha256_mismatch:{shard}")
        payload=json.loads(raw)
        for entry in payload.get("items",[]):
            item=entry.get("item",{})
            if item.get("source")!="gem": continue
            expected=registry_by_id.get(item.get("id")); actual=candidate_sha256(item)
            if expected is None or actual!=entry.get("candidate_sha256") or actual!=expected.get("candidate_sha256"): raise ValueError(f"gem_candidate_identity_mismatch:{item.get('id')}")
            item["bootstrap_eligible"]=bool(expected.get("bootstrap_expected")); items.append(item)
    if len(items)!=458: raise ValueError(f"gem_series_count_mismatch:{len(items)}")
    return items

def _load_pink(state:dict,registry_by_id:dict):
    pink_source=next((x for x in state["manifest_seed"]["sources"] if x.get("provider")=="World Bank Pink Sheet"),None)
    if not pink_source or pink_source.get("sha256")!=PINK_SHA: raise ValueError("pink_source_reference_mismatch")
    request=urllib.request.Request(pink_source["url"],headers={"User-Agent":"CHAOS-P2-B/1.0","Accept":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"})
    with urllib.request.urlopen(request,timeout=90) as response: workbook=response.read()
    if hashlib.sha256(workbook).hexdigest()!=PINK_SHA: raise ValueError("pink_workbook_sha256_mismatch")
    parsed,_layout=source.parse_pink(workbook); del workbook
    items=[]
    for name,mapping in sorted(parsed.items()):
        months,levels=source.longest_run(mapping); axis,values=source.returns(months,levels); quality=source.g0(values,501)
        if not quality.get("passed"): continue
        identifier="pink:"+source.clean(name); expected=registry_by_id.get(identifier)
        if expected is None: continue
        item={"id":identifier,"source":"pink_sheet","source_name":"World Bank Pink Sheet","name":name,
              "cohort":expected["item_metadata"]["cohort"],"domain":expected["item_metadata"]["domain"],
              "frequency":expected["item_metadata"]["frequency"],"axis":axis,"values":values,
              "sha256":PINK_SHA,"points":len(levels)}
        if candidate_sha256(item)!=expected["candidate_sha256"]: raise ValueError(f"pink_candidate_identity_mismatch:{identifier}")
        item["bootstrap_eligible"]=bool(expected.get("bootstrap_expected")); items.append(item)
    if len(items)!=51: raise ValueError(f"pink_series_count_mismatch:{len(items)}")
    return items

def load_p2_economic_series(prepared_zip:str|Path):
    path=Path(prepared_zip); artifact_sha=hashlib.sha256(path.read_bytes()).hexdigest()
    if artifact_sha!=ARTIFACT_SHA: raise ValueError("prepared_artifact_sha256_mismatch")
    with zipfile.ZipFile(path) as archive:
        state,registry,registry_by_id=_load_registry(archive)
        gem=_load_gem(archive,state,registry_by_id)
    pink=_load_pink(state,registry_by_id); series=pink+gem
    if len(series)!=509 or len({x["id"] for x in series})!=509: raise ValueError("economic_cohort_count_or_identity_mismatch")
    for item in series:
        if len(item["axis"])!=len(item["values"]) or len(item["values"])<87: raise ValueError(f"economic_series_length_or_axis_invalid:{item['id']}")
    counts={"series":509,"pink_sheet":51,"gem":458,
            "null_eligible":sum(bool(x["bootstrap_eligible"]) for x in series),
            "null_eligible_pink_sheet":sum(bool(x["bootstrap_eligible"]) for x in pink),
            "null_eligible_gem":sum(bool(x["bootstrap_eligible"]) for x in gem),
            "null_ineligible":sum(not bool(x["bootstrap_eligible"]) for x in series),
            "source_commit":RUN_SHA,"prepared_artifact_sha256":ARTIFACT_SHA,
            "pink_source_sha256":PINK_SHA,"pink_raw_values_persisted":False,
            "gem_values_source":"pinned_candidate_shards_from_prepare_artifact"}
    if (counts["null_eligible"],counts["null_eligible_pink_sheet"],counts["null_eligible_gem"])!=(359,48,311): raise ValueError("null_eligibility_counts_mismatch")
    return series,counts
