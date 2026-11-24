"""P2.2 real-data stress pipeline. Frozen BreakDetectorV1 is imported and never edited."""
from __future__ import annotations
import csv, hashlib, json, math, os, re, time, urllib.parse, urllib.request, warnings
from collections import defaultdict, Counter
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from importlib.metadata import metadata as package_metadata, PackageNotFoundError, version as package_version
import sys
import numpy as np
from openpyxl import load_workbook
from statsmodels.tsa.stattools import adfuller, kpss
from structural_engine.isolated_break_detector_v1 import BreakDetectorV1, DEFAULT_MARKOV_THRESHOLD

ROOT=Path(__file__).resolve().parents[1]
HERE=Path(__file__).resolve().parent
RAW=ROOT/"artifacts"/"real_data_stress"/"raw"
DERIVED=ROOT/"artifacts"/"real_data_stress"/"derived"
OUT=HERE/"results"; REPORT=ROOT/"REAL_DATA_STRESS_REPORT_AR.md"
MANIFEST=OUT/"real_data_stress_manifest.json"; CHECKSUMS=OUT/"SHA256SUMS.txt"; DEPENDENCIES=OUT/"dependency_manifest.json"
PIPELINE_CONFIG=json.loads((HERE/"config"/"pipeline.json").read_text(encoding="utf-8"))
GEM_CONFIG=json.loads((HERE/"config"/"gem_indicators.json").read_text(encoding="utf-8"))
SEISMIC_CONFIG=json.loads((HERE/"config"/"seismic_belts.json").read_text(encoding="utf-8"))
TIME_SUPPORT_SCHEMA_PATH=ROOT/"observation_foundation"/"contracts"/"observation_time_support_v1.schema.json"
TIME_SUPPORT_SCHEMA=json.loads(TIME_SUPPORT_SCHEMA_PATH.read_text(encoding="utf-8"))
STATIONARITY_CONFIG=PIPELINE_CONFIG["stationarity"]
BOOTSTRAP_CONFIG=PIPELINE_CONFIG["bootstrap"]
STATIONARITY_MIN_OBSERVATIONS=int(PIPELINE_CONFIG["general_g0_min_observations_inclusive"])
STATIONARITY_ADF_SIGNIFICANCE=float(STATIONARITY_CONFIG["adf_significance"])
STATIONARITY_KPSS_SIGNIFICANCE=float(STATIONARITY_CONFIG["kpss_significance"])
LEVEL_NULL_FAMILY=str(STATIONARITY_CONFIG["level_null_family"])
INTEGRATED_NULL_FAMILY=str(STATIONARITY_CONFIG["integrated_null_family"])
INTEGRATED_NULL_DOMAINS=frozenset(STATIONARITY_CONFIG["integrated_null_domain_allowlist"])
INTEGRATED_ADF_SIGNIFICANCE=float(STATIONARITY_CONFIG["integrated_null_requires_first_difference_adf_p_less_than"])
INTEGRATED_KPSS_SIGNIFICANCE=float(STATIONARITY_CONFIG["integrated_null_requires_first_difference_kpss_p_greater_equal"])
SEISMIC_NULL_POLICY=str(STATIONARITY_CONFIG["seismic_null_policy"])
if STATIONARITY_CONFIG["detector_execution_requires_stationarity"] is not False:
 raise ValueError("pipeline_config_invalid: observed-series detector execution must not require stationarity")
if BOOTSTRAP_CONFIG["seismic_generic_bootstrap_enabled"] is not False:
 raise ValueError("pipeline_config_invalid: generic seismic stationary bootstrap must remain disabled")
if not INTEGRATED_NULL_DOMAINS or not INTEGRATED_NULL_DOMAINS.issubset({"macro","commodity"}):
 raise ValueError("pipeline_config_invalid: integrated null domain allowlist is unsafe")
if not all(0.0<value<1.0 for value in (
 STATIONARITY_ADF_SIGNIFICANCE,STATIONARITY_KPSS_SIGNIFICANCE,
 INTEGRATED_ADF_SIGNIFICANCE,INTEGRATED_KPSS_SIGNIFICANCE
)):
 raise ValueError("pipeline_config_invalid: stationarity significance levels must be in (0,1)")
if BOOTSTRAP_CONFIG["conditional_alarm_probability_only"] is not True:
 raise ValueError("pipeline_config_invalid: bootstrap metrics must remain conditional alarm probabilities")
if BOOTSTRAP_CONFIG["operational_fpr_claim_permitted"] is not False:
 raise ValueError("pipeline_config_invalid: operational FPR claims are prohibited without ground truth")
Y0,Y1=int(PIPELINE_CONFIG["period_start"][:4]),int(PIPELINE_CONFIG["period_end"][:4])
PINK_MIN=int(os.getenv("STRESS_MIN_COMMODITY_POINTS",str(int(PIPELINE_CONFIG["primary_monthly_min_observations_exclusive"])+1)))
GEM_MIN=int(os.getenv("STRESS_MIN_GEM_POINTS",str(GEM_CONFIG.get("minimum_observations",PIPELINE_CONFIG["world_bank"]["gem_general_min_observations"]))))
SEISMIC_MIN=int(PIPELINE_CONFIG["general_g0_min_observations_inclusive"])
REPS=int(os.getenv("STRESS_BOOTSTRAP_REPLICATES",str(PIPELINE_CONFIG["bootstrap"]["replicates"])))
MONTH_BLOCK=int(os.getenv("STRESS_BOOTSTRAP_MEAN_BLOCK_MONTHS",str(PIPELINE_CONFIG["bootstrap"]["market_mean_block_length"])))
EVENT_BLOCK=int(os.getenv("STRESS_BOOTSTRAP_MEAN_BLOCK_EVENTS",str(PIPELINE_CONFIG["bootstrap"]["seismic_mean_block_length_events"])))
MAG=float(os.getenv("STRESS_USGS_MIN_MAGNITUDE",str(SEISMIC_CONFIG["minimum_magnitude"])))
USGS_QUERY_LIMIT=int(SEISMIC_CONFIG["query_limit"])
USGS_RETRIES=int(PIPELINE_CONFIG["usgs"]["retry_attempts"])
USGS_TIMEOUT=int(PIPELINE_CONFIG["usgs"]["timeout_seconds"])
GEM_SOURCE_ID=int(GEM_CONFIG["world_bank_source_id"])
GEM_PERIOD_WINDOW=str(GEM_CONFIG["period_window"])
H=DEFAULT_MARKOV_THRESHOLD
UA="CHAOS-P2.2/1.0 https://github.com/uniqueteamyemen/CHAOS"
LANDING="https://www.worldbank.org/en/research/commodity-markets"
PINK_FALLBACK="https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx"
GEM={item["code"]:item["description"] for item in GEM_CONFIG["indicators"]}
BELTS=SEISMIC_CONFIG["belts"]


def dependency_inventory():
 names=("numpy","openpyxl","statsmodels","scipy","pandas","patsy","packaging","formulaic","interface-meta","python-dateutil","pytz","tzdata")
 packages={}
 for name in names:
  try:
   meta=package_metadata(name)
   packages[name]={"version":package_version(name),"license_expression":meta.get("License-Expression"),"license":meta.get("License"),"home_page":meta.get("Home-page")}
  except PackageNotFoundError:
   packages[name]={"status":"not_installed"}
 return {"python_version":sys.version,"python_implementation":sys.implementation.name,"packages":packages}
def stamp(): return datetime.now(timezone.utc).isoformat()
def digest(b): return hashlib.sha256(b).hexdigest()
def hash_file(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for x in iter(lambda:f.read(1024*1024),b""):h.update(x)
 return h.hexdigest()
def get(url,retries=USGS_RETRIES,timeout=USGS_TIMEOUT):
 err=None
 for i in range(retries):
  try:
   req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"*/*"})
   with urllib.request.urlopen(req,timeout=timeout) as r:
    data=r.read()
    if r.status!=200 or not data:raise RuntimeError(f"HTTP {r.status}, empty={not data}")
    return data
  except Exception as e:
   err=e
   if i+1<retries:time.sleep(2**i)
 raise RuntimeError(f"GET failed {url}: {err}")
def keep_raw(rel,data,provider,url,params=None,time_support=None):
 p=RAW/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 resolved_path=p.resolve()
 try:
  recorded_path=str(resolved_path.relative_to(ROOT.resolve()))
 except ValueError:
  recorded_path=str(resolved_path)
 record={"path":recorded_path,"sha256":digest(data),"bytes":len(data),"provider":provider,"url":url,"parameters":params or {},"retrieved_at_utc":stamp()}
 if time_support is not None:
  record["time_support"]=time_support
 return record
def clean(s):return re.sub(r"[^A-Za-z0-9_.-]+","_",str(s)).strip("._")[:100] or "series"
def number(v):
 if v is None:return None
 if isinstance(v,(float,int)):x=float(v)
 else:
  s=str(v).strip().replace(",","")
  if s in {"","...","..","—","-","NA","N/A"}:return None
  try:x=float(s)
  except ValueError:return None
 return x if math.isfinite(x) else None
def month(v):
 s=str(v).strip()
 m=re.fullmatch(r"(\d{4})[-/]?\s*M\s*(\d{1,2})",s,re.I) or re.fullmatch(r"(\d{4})[-/](\d{1,2})",s) or re.fullmatch(r"(\d{4})(\d{2})",s)
 if not m:return None
 y,k=map(int,m.groups())
 return y*12+k-1 if 1<=k<=12 else None
def label_month(n):
 y,m=divmod(int(n),12);return f"{y:04d}-{m+1:02d}"


def make_time_support(start, end, native_frequency, boundary_semantics):
 required=set(TIME_SUPPORT_SCHEMA.get("required", []))
 properties=TIME_SUPPORT_SCHEMA.get("properties", {})
 support={
  "observation_period_start":str(start),
  "observation_period_end":str(end),
  "native_frequency":str(native_frequency),
  "boundary_semantics":str(boundary_semantics),
 }
 if not required.issubset(support):
  raise ValueError("observation_time_support_missing_required_fields")
 if set(support)-set(properties):
  raise ValueError("observation_time_support_schema_property_mismatch")
 if any(not isinstance(support[key],str) or not support[key].strip() for key in required):
  raise ValueError("observation_time_support_empty_required_value")
 if not support["boundary_semantics"].strip():
  raise ValueError("observation_time_support_boundary_semantics_empty")
 return support


def _utc_iso(value):
 parsed=datetime.fromisoformat(str(value).replace("Z","+00:00"))
 if parsed.tzinfo is None:
  parsed=parsed.replace(tzinfo=timezone.utc)
 return parsed.astimezone(timezone.utc).isoformat().replace("+00:00","Z")


def time_support_registry():
 gem_start_token,separator,gem_end_token=GEM_PERIOD_WINDOW.partition(":")
 if not separator:
  raise ValueError("gem_period_window_must_have_start_and_end")
 gem_start_index=month(gem_start_token)
 gem_end_index=month(gem_end_token)
 if gem_start_index is None or gem_end_index is None:
  raise ValueError("gem_period_window_must_use_explicit_months")
 pink_support=make_time_support(
  PIPELINE_CONFIG["period_start"],
  PIPELINE_CONFIG["period_end"],
  "monthly",
  "PIPELINE_ANALYSIS_FILTER_WINDOW_INCLUSIVE; SOURCE_COVERAGE_NOT_ASSERTED",
 )
 gem_support=make_time_support(
  label_month(gem_start_index),
  label_month(gem_end_index),
  "monthly",
  "WORLD_BANK_API_QUERY_WINDOW_START_AND_END_INCLUSIVE; SOURCE_COVERAGE_NOT_ASSERTED",
 )
 usgs_start=_utc_iso(f"{Y0}-01-01T00:00:00")
 usgs_end=_utc_iso(f"{Y1+1}-01-01T00:00:00")
 usgs_support=make_time_support(
  usgs_start,
  usgs_end,
  "event_timestamp",
  f"USGS_COMCAT_QUERY_WINDOW_START_INCLUSIVE_END_EXCLUSIVE; MINIMUM_MAGNITUDE_QUERY_THRESHOLD={MAG}; NOT_MAGNITUDE_COMPLETENESS",
 )
 return {
  "schema_id":TIME_SUPPORT_SCHEMA.get("$id"),
  "schema_path":TIME_SUPPORT_SCHEMA_PATH.relative_to(ROOT).as_posix(),
  "scope":"source_collection",
  "record_identity_hash_impact":"NONE",
  "sources":{
   "pink_sheet":{
    "time_support":pink_support,
    "source_coverage_status":"NOT_ASSERTED_FROM_ANALYSIS_FILTER_WINDOW",
   },
   "gem":{
    "time_support":gem_support,
    "source_coverage_status":"NOT_ASSERTED_FROM_API_QUERY_WINDOW",
   },
   "usgs":{
    "by_belt":{
     belt["id"]:{
      "time_support":dict(usgs_support),
      "source_coverage_status":"NOT_ASSERTED_FROM_API_QUERY_WINDOW",
      "minimum_magnitude_query_threshold":MAG,
      "magnitude_completeness_status":"NOT_ESTABLISHED_BY_QUERY_THRESHOLD",
     }
     for belt in BELTS
    },
   },
  },
 }


TIME_SUPPORT_REGISTRY=time_support_registry()
PINK_TIME_SUPPORT=TIME_SUPPORT_REGISTRY["sources"]["pink_sheet"]["time_support"]
GEM_TIME_SUPPORT=TIME_SUPPORT_REGISTRY["sources"]["gem"]["time_support"]
USGS_TIME_SUPPORT_BY_BELT={
 belt_id:entry["time_support"]
 for belt_id,entry in TIME_SUPPORT_REGISTRY["sources"]["usgs"]["by_belt"].items()
}


def mad(x):
 a=np.asarray(x,dtype=float)
 return float(np.median(np.abs(a-np.median(a)))) if a.size and np.all(np.isfinite(a)) else 0.
def g0(x,n):
 a=np.asarray(x,dtype=float)
 if a.ndim!=1 or not np.all(np.isfinite(a)):return {"passed":False,"reason":"nonfinite_or_nonvector"}
 if len(a)<n:return {"passed":False,"reason":"insufficient_observations","observations":len(a),"required":n}
 if len(a)<52:return {"passed":False,"reason":"below_detector_minimum"}
 dm,lm=mad(np.diff(a[:40])),mad(a[:40])
 if dm<=1e-10:return {"passed":False,"reason":"degenerate_baseline_diff_mad","baseline_diff_mad":dm,"baseline_level_mad":lm}
 if lm<=1e-10:return {"passed":False,"reason":"degenerate_baseline_level_mad","baseline_diff_mad":dm,"baseline_level_mad":lm}
 return {"passed":True,"observations":len(a),"minimum":n,"baseline_diff_mad":dm,"baseline_level_mad":lm}
def g1(x,adf_significance=None,kpss_significance=None):
 adf_alpha=STATIONARITY_ADF_SIGNIFICANCE if adf_significance is None else float(adf_significance)
 kpss_alpha=STATIONARITY_KPSS_SIGNIFICANCE if kpss_significance is None else float(kpss_significance)
 if not (0.0<adf_alpha<1.0 and 0.0<kpss_alpha<1.0):
  return {"passed":False,"status":"INVALID_TEST_CONFIGURATION","reason":"significance_must_be_in_0_1"}
 a=np.asarray(x,dtype=float)
 if a.ndim!=1 or not np.all(np.isfinite(a)):
  return {"passed":False,"status":"INVALID_INPUT","reason":"nonfinite_or_nonvector","observations":int(a.size)}
 if len(a)<STATIONARITY_MIN_OBSERVATIONS:
  return {"passed":False,"status":"NOT_TESTED","reason":f"fewer_than_{STATIONARITY_MIN_OBSERVATIONS}_observations","observations":int(len(a))}
 if mad(a)<=1e-10:
  return {"passed":False,"status":"DEGENERATE","reason":"degenerate_series_mad","observations":int(len(a))}
 try:
  with warnings.catch_warnings(record=True) as caught:
   warnings.simplefilter("always")
   adf_result=adfuller(a,regression="c",autolag="AIC")
   kpss_result=kpss(a,regression="c",nlags="auto")
  adf_p=float(adf_result[1]);kpss_p=float(kpss_result[1])
  adf_ok=adf_p<adf_alpha
  kpss_ok=kpss_p>=kpss_alpha
  passed=bool(adf_ok and kpss_ok)
  return {
   "passed":passed,
   "status":"SCREEN_PASS" if passed else "SCREEN_FAIL",
   "observations":int(len(a)),
   "adf_statistic":float(adf_result[0]),
   "adf_p_value":adf_p,
   "adf_lags":int(adf_result[2]),
   "adf_rejects_unit_root":adf_ok,
   "kpss_statistic":float(kpss_result[0]),
   "kpss_p_value":kpss_p,
   "kpss_lags":int(kpss_result[2]),
   "kpss_does_not_reject_level_stationarity":kpss_ok,
   "significance":adf_alpha,
   "adf_significance":adf_alpha,
   "kpss_significance":kpss_alpha,
   "warnings":[str(item.message) for item in caught],
   "interpretation":"Conservative preliminary stationarity screen only; passing ADF and KPSS does not prove strict stationarity or validate a domain-specific stochastic model."
  }
 except Exception as exc:
  return {"passed":False,"status":"TEST_ERROR","observations":int(len(a)),"reason":f"{type(exc).__name__}:{exc}"}
def longest_run(mapping):
 runs=[];r=[]
 for k,v in sorted(mapping.items()):
  if r and k!=r[-1][0]+1:runs.append(r);r=[]
  r.append((k,v))
 if r:runs.append(r)
 r=max(runs,key=len) if runs else []
 return [k for k,v in r],[v for k,v in r]
def returns(months,levels):
 if len(levels)<2 or any(v<=0 for v in levels):return [],[]
 return [label_month(m) for m in months[1:]],[math.log(levels[i]/levels[i-1]) for i in range(1,len(levels))]
def discover_pink():
 try:
  html=get(LANDING,2,40).decode("utf-8","replace")
  links=re.findall(r"""href\s*=\s*["']([^"']*CMO-Historical-Data-Monthly\.xlsx[^"']*)["']""",html,re.I)
  if links:return urllib.parse.urljoin(LANDING,links[0].replace("&amp;","&")),"dynamic_official_page_link"
 except Exception:pass
 return PINK_FALLBACK,"versioned_fallback_after_dynamic_discovery_failure"
def parse_pink(data):
 wb=load_workbook(BytesIO(data),read_only=True,data_only=True)
 ws=next((s for s in wb.worksheets if s.title.strip().casefold()=="monthly prices"),None)
 if ws is None:raise ValueError("Pink Sheet workbook does not contain Monthly Prices")
 rows=list(ws.iter_rows(values_only=True));first=next((i for i,r in enumerate(rows) if r and month(r[0]) is not None),None)
 if first is None:raise ValueError("Pink Sheet monthly date column not found")
 # Native Pink Sheet has two physical header rows: commodity code/name,
 # followed by units. The row immediately above the first YYYYМmm record is
 # the units row, NOT the commodity-name row.
 header_index=first-2
 units_index=first-1
 if header_index<0:raise ValueError("Pink Sheet two-row header not found before first monthly record")
 header=rows[header_index];units=rows[units_index] if units_index>=0 else ()
 out=defaultdict(dict);count=0;unit_map={}
 for row in rows[first:]:
  if not row:continue
  m=month(row[0])
  if m is None or not Y0*12<=m<(Y1+1)*12:continue
  count+=1
  for j,v in enumerate(row[1:],1):
   x=number(v)
   if x is None:continue
   raw_name=header[j] if j<len(header) else None
   name=str(raw_name).strip() if raw_name is not None else ""
   if not name or name.casefold() in {"none","nan"}:continue
   unit=units[j] if j<len(units) and units[j] is not None else None
   if name in out and unit_map.get(name)!=unit:
    raise ValueError(f"duplicate_native_series_header_with_conflicting_units:{name}")
   unit_map[name]=str(unit).strip() if unit is not None else None
   out[name][m]=x
 wb.close()
 return dict(out),{"sheet":"Monthly Prices","first_data_row":first+1,"commodity_header_row":header_index+1,"units_row":units_index+1,"monthly_rows":count,"series_columns":len(out),"units_by_series":unit_map}
def pink(m):
 url,discovery=discover_pink()
 try:
  raw=get(url)
  # The current Pink Sheet workbook's workbook-specific redistribution terms are
  # not asserted here. Keep the bytes in-memory; publish only hash and derived
  # audit outputs until terms are verified.
  sh=digest(raw);parsed,layout=parse_pink(raw);items=[]
  for name,mapping in sorted(parsed.items()):
   xs,ys=longest_run(mapping);axis,vals=returns(xs,ys);q=g0(vals,PINK_MIN)
   if not q["passed"]:
    m["rejected"].append({"source":"pink_sheet","series":name,"source_points":len(ys),"quality":q});continue
   items.append({"id":"pink:"+clean(name),"source":"pink_sheet","source_name":"World Bank Pink Sheet","name":name,"cohort":"strict_long_monthly","domain":"commodity","frequency":"monthly","axis":axis,"values":vals,"sha256":sh,"points":len(ys),"quality":q})
  m["sources"].append({"provider":"World Bank Pink Sheet","url":url,"discovery":discovery,"sha256":sh,"bytes":len(raw),"retrieved_at_utc":stamp(),"raw_preserved":"in-memory only; workbook-specific redistribution terms not established","layout":layout,"accepted_series":len(items),"time_support":PINK_TIME_SUPPORT})
  return items
 except Exception as e:
  m["errors"].append({"provider":"World Bank Pink Sheet","url":url,"error":str(e),"time":stamp()});return []
def gem(m):
 out=[]
 for code,desc in GEM.items():
  page=1;pages=1;groups=defaultdict(dict);names={};hashes=[]
  try:
   while page<=pages:
    q=urllib.parse.urlencode({"source":GEM_SOURCE_ID,"format":"json","per_page":20000,"page":page,"date":GEM_PERIOD_WINDOW})
    url=f"https://api.worldbank.org/v2/country/all/indicator/{code}?{q}"
    raw=get(url,3);obj=json.loads(raw)
    if not isinstance(obj,list) or len(obj)<2 or not isinstance(obj[0],dict):raise ValueError("unexpected API response")
    pages=int(obj[0].get("pages",1));rows=obj[1]
    if not isinstance(rows,list):raise ValueError("API has no data rows")
    rec=keep_raw(f"world_bank/gem/{code}_page_{page:03d}.json",raw,"World Bank GEM",url,{"source":GEM_SOURCE_ID,"indicator":code,"page":page},GEM_TIME_SUPPORT)
    m["sources"].append(rec);hashes.append(rec["sha256"])
    for row in rows:
     k=month(row.get("date"));v=number(row.get("value"))
     if k is None or v is None or not Y0*12<=k<(Y1+1)*12:continue
     country=row.get("country") or {};iso=str(row.get("countryiso3code") or country.get("id") or "UNK");names[iso]=str(country.get("value") or iso);groups[iso][k]=v
    page+=1
   for iso,mapping in groups.items():
    xs,ys=longest_run(mapping);axis,vals=returns(xs,ys);q=g0(vals,GEM_MIN)
    if not q["passed"]:
     m["rejected"].append({"source":"gem","series":f"{code}:{iso}","quality":q});continue
    out.append({"id":f"gem:{code}:{iso}","source":"gem","source_name":"World Bank GEM","name":f"{desc} — {names[iso]}","cohort":"secondary_gem_monthly_87_plus","domain":"macro","frequency":"monthly","axis":axis,"values":vals,"sha256":hashes[0] if hashes else None,"points":len(ys),"quality":q})
   accepted_for_code=sum(1 for x in out if x["id"].startswith("gem:"+code+":"))
   summary={"code":code,"description":desc,"date_query":GEM_PERIOD_WINDOW,"frequency_policy":"monthly-only by actual year-month response keys; frequency query parameter omitted because World Bank documents frequency as an MRV modifier","records_with_monthly_dates":sum(map(len,groups.values())),"country_series":len(groups),"accepted":accepted_for_code,"raw_hashes":hashes,"status":"monthly_data_found" if groups else "no_monthly_records_for_indicator","time_support":GEM_TIME_SUPPORT}
   m["gem_indicators"].append(summary)
   print("GEM",code,"monthly_records",summary["records_with_monthly_dates"],"country_series",summary["country_series"],"accepted",accepted_for_code)
  except Exception as e:
   error_record={"provider":"World Bank GEM","indicator":code,"error":str(e),"time":stamp()}
   m["errors"].append(error_record)
   m["gem_indicators"].append({"code":code,"description":desc,"status":"api_error","error":str(e)})
   print("GEM ERROR",code,type(e).__name__,str(e))
 return out
def usgs_query(belt,start,end,m,depth=0):
 p={"format":"geojson","starttime":start,"endtime":end,"minmagnitude":MAG,"minlatitude":belt["minlatitude"],"maxlatitude":belt["maxlatitude"],"minlongitude":belt["minlongitude"],"maxlongitude":belt["maxlongitude"],"orderby":"time-asc","limit":USGS_QUERY_LIMIT}
 url="https://earthquake.usgs.gov/fdsnws/event/1/query?"+urllib.parse.urlencode(p)
 raw=get(url,4,120);request_support=make_time_support(_utc_iso(start),_utc_iso(end),"event_timestamp",f"USGS_COMCAT_QUERY_WINDOW_START_INCLUSIVE_END_EXCLUSIVE; MINIMUM_MAGNITUDE_QUERY_THRESHOLD={MAG}; NOT_MAGNITUDE_COMPLETENESS");r=keep_raw(f"usgs/{belt['id']}/{start.replace(':','_')}_{end.replace(':','_')}.geojson",raw,"USGS ComCat",url,p,request_support);m["sources"].append(r)
 fs=json.loads(raw).get("features",[])
 if len(fs)>=19999:
  a=datetime.fromisoformat(start);b=datetime.fromisoformat(end)
  if (b-a).total_seconds()<86400 or depth>=12:raise RuntimeError("catalog query remains saturated at minimum interval")
  mid=(a+(b-a)/2).strftime("%Y-%m-%dT%H:%M:%S")
  return usgs_query(belt,start,mid,m,depth+1)+usgs_query(belt,mid,end,m,depth+1)
 return fs
def usgs_record_rejection_reasons(
 belt, latitude, longitude, magnitude, epoch_ms, min_magnitude=None
):
 reasons=[]
 def finite_number(value):
  if isinstance(value,bool) or value is None:return None
  try:number=float(value)
  except (TypeError,ValueError,OverflowError):return None
  return number if math.isfinite(number) else None
 lat=finite_number(latitude);lon=finite_number(longitude);mag=finite_number(magnitude)
 if lat is None or lon is None:
  reasons.append("INVALID_OR_MISSING_COORDINATES")
 else:
  if not (-90.0<=lat<=90.0 and -180.0<=lon<=180.0):
   reasons.append("COORDINATES_OUT_OF_GLOBAL_RANGE")
  else:
   if not (float(belt["minlatitude"])<=lat<=float(belt["maxlatitude"])):
    reasons.append("OUTSIDE_BELT_LATITUDE_BOUNDS")
   min_lon=float(belt["minlongitude"]);max_lon=float(belt["maxlongitude"])
   inside_lon=(min_lon<=lon<=max_lon) if min_lon<=max_lon else (lon>=min_lon or lon<=max_lon)
   if not inside_lon:reasons.append("OUTSIDE_BELT_LONGITUDE_BOUNDS")
 if mag is None:
  reasons.append("INVALID_OR_MISSING_MAGNITUDE")
 else:
  threshold=float(MAG if min_magnitude is None else min_magnitude)
  if mag<threshold:reasons.append("BELOW_QUERY_MINIMUM_MAGNITUDE")
 try:
  if isinstance(epoch_ms,bool) or epoch_ms is None:raise ValueError
  if isinstance(epoch_ms,int):event_ms=epoch_ms
  elif isinstance(epoch_ms,float) and math.isfinite(epoch_ms) and epoch_ms.is_integer():
   event_ms=int(epoch_ms)
  elif isinstance(epoch_ms,str) and epoch_ms.strip().lstrip("+-").isdigit():
   event_ms=int(epoch_ms.strip())
  else:raise ValueError
 except (TypeError,ValueError,OverflowError):
  reasons.append("INVALID_OR_MISSING_EVENT_TIME")
 else:
  window_start=int(datetime(Y0,1,1,tzinfo=timezone.utc).timestamp()*1000)
  window_end=int(datetime(Y1+1,1,1,tzinfo=timezone.utc).timestamp()*1000)
  if not (window_start<=event_ms<window_end):
   reasons.append("OUTSIDE_ANALYSIS_TIME_WINDOW")
 return reasons


def seismic(m):
 out=[]
 for belt in BELTS:
  try:
   fs=usgs_query(belt,f"{Y0}-01-01T00:00:00",f"{Y1+1}-01-01T00:00:00",m)
   events={}
   rejected_count=0
   duplicate_count=0
   rejected_by_reason=Counter()
   magnitude_type_counts=Counter()
   magnitude_source_counts=Counter()
   for feature_index,feature in enumerate(fs):
    if not isinstance(feature,dict):
     feature={}
    properties=feature.get("properties")
    if not isinstance(properties,dict):
     properties={}
    geometry=feature.get("geometry")
    if not isinstance(geometry,dict):
     geometry={}
    coordinates=geometry.get("coordinates")
    if not isinstance(coordinates,(list,tuple)):
     coordinates=[]
    longitude=coordinates[0] if len(coordinates)>=2 else None
    latitude=coordinates[1] if len(coordinates)>=2 else None
    raw_time=properties.get("time")
    raw_magnitude=properties.get("mag")
    raw_mag_type=properties.get("magType")
    mag_type=str(raw_mag_type).strip().lower() if raw_mag_type is not None and str(raw_mag_type).strip() else "missing"
    raw_mag_source=properties.get("magSource")
    mag_source=str(raw_mag_source).strip() if raw_mag_source is not None and str(raw_mag_source).strip() else "missing"
    reasons=usgs_record_rejection_reasons(
     belt,latitude,longitude,raw_magnitude,raw_time,MAG
    )
    raw_event_id=feature.get("id")
    if raw_event_id is not None and str(raw_event_id).strip():
     event_id=str(raw_event_id).strip()
    elif any(value is not None for value in (raw_time,raw_magnitude,longitude,latitude)):
     event_id=f"fallback:{raw_time}:{raw_magnitude}:{longitude}:{latitude}"
    else:
     event_id=f"feature-index:{feature_index}"
    if reasons:
     rejected_count+=1
     for reason in reasons:rejected_by_reason[reason]+=1
     m["rejected"].append({
      "source":"usgs","series":belt["id"],"event_id":event_id,
      "reasons":reasons,"time":raw_time,"magnitude":raw_magnitude,
      "longitude":longitude,"latitude":latitude,"place":properties.get("place"),
      "handling":"QUARANTINED_FROM_ANALYTICAL_CATALOG_RAW_SOURCE_PRESERVED",
     })
     continue
    epoch=int(raw_time)
    magnitude=float(raw_magnitude)
    longitude=float(longitude)
    latitude=float(latitude)
    depth=None
    if len(coordinates)>2 and coordinates[2] is not None:
     try:
      candidate_depth=float(coordinates[2])
      if math.isfinite(candidate_depth):depth=candidate_depth
     except (TypeError,ValueError,OverflowError):
      depth=None
    event={
     "id":event_id,
     "time":datetime.fromtimestamp(epoch/1000,tz=timezone.utc).isoformat(),
     "epoch_ms":epoch,"magnitude":magnitude,
     "longitude":longitude,"latitude":latitude,
     "depth_km":depth,"place":properties.get("place"),
     "mag_type":mag_type,"mag_source":mag_source,
    }
    previous=events.get(event_id)
    if previous is not None:
     if previous==event:
      duplicate_count+=1
      continue
     rejected_count+=1
     rejected_by_reason["DUPLICATE_EVENT_ID_CONFLICT"]+=1
     m["rejected"].append({
      "source":"usgs","series":belt["id"],"event_id":event_id,
      "reasons":["DUPLICATE_EVENT_ID_CONFLICT"],
      "time":raw_time,"magnitude":raw_magnitude,
      "longitude":longitude,"latitude":latitude,
      "handling":"QUARANTINED_CONFLICTING_DUPLICATE_RAW_SOURCE_PRESERVED",
     })
     continue
    events[event_id]=event
    magnitude_type_counts[mag_type]+=1
    magnitude_source_counts[mag_source]+=1
   rows=sorted(events.values(),key=lambda x:x["epoch_ms"])
   if len(fs) != len(rows) + rejected_count + duplicate_count:
    raise RuntimeError(
     "USGS catalog accounting mismatch: "
     f"received={len(fs)}, accepted={len(rows)}, "
     f"quarantined={rejected_count}, deduplicated={duplicate_count}"
    )
   csvpath=DERIVED/f"{belt['id']}_events.csv";csvpath.parent.mkdir(parents=True,exist_ok=True)
   cols=["id","time","epoch_ms","magnitude","longitude","latitude","depth_km","place","mag_type","mag_source"]
   with csvpath.open("w",newline="",encoding="utf-8") as handle:
    writer=csv.DictWriter(handle,fieldnames=cols);writer.writeheader();writer.writerows(rows)
   catalog_integrity_status="PASS_WITH_QUARANTINE" if rejected_count else "PASS"
   rec={
    "id":belt["id"],"name":belt["name"],
    "bbox":{k:belt[k] for k in ("minlatitude","maxlatitude","minlongitude","maxlongitude")},
    "min_magnitude":MAG,"minimum_magnitude_query_threshold":MAG,"magnitude_completeness_status":"NOT_ESTABLISHED_BY_QUERY_THRESHOLD","time_support":USGS_TIME_SUPPORT_BY_BELT[belt["id"]],"events":len(rows),
    "events_received":len(fs),"events_accepted":len(rows),
    "events_quarantined":rejected_count,
    "duplicate_features_deduplicated":duplicate_count,
    "rejected_by_reason":dict(sorted(rejected_by_reason.items())),
    "magnitude_type_counts":dict(sorted(magnitude_type_counts.items())),
    "magnitude_source_counts":dict(sorted(magnitude_source_counts.items())),
    "magnitude_type_missing_events":magnitude_type_counts.get("missing",0),
    "magnitude_source_missing_events":magnitude_source_counts.get("missing",0),
    "magnitude_source_homogeneous":len([k for k in magnitude_source_counts if k!="missing"])==1 and magnitude_source_counts.get("missing",0)==0,
    "magnitude_source_mixture_requires_calibration_review":len([k for k in magnitude_source_counts if k!="missing"])>1 or magnitude_source_counts.get("missing",0)>0,
    "magnitude_type_homogeneous":len([k for k in magnitude_type_counts if k!="missing"])==1 and magnitude_type_counts.get("missing",0)==0,
    "single_magnitude_type_precheck_pass":len(magnitude_type_counts)==1 and "missing" not in magnitude_type_counts,
    "catalog_integrity_status":catalog_integrity_status,
    "client_side_validation":"coordinates_magnitude_and_analysis_time_rechecked",
    "start":rows[0]["time"] if rows else None,
    "end":rows[-1]["time"] if rows else None,
    "csv_sha256":hash_file(csvpath),
   }
   m["belts"].append(rec)
   # Secondary monthly event-count representation; empty months are zero only
   # inside the fully queried and client-side-validated USGS catalog window.
   month_counts={k:0 for k in range(Y0*12,(Y1+1)*12)}
   for event in rows:
    k=month(event["time"][:7])
    if k in month_counts:month_counts[k]+=1
   monthly_axis=[label_month(k) for k in month_counts]
   monthly_values=[math.log1p(month_counts[k]) for k in month_counts]
   monthly_quality=g0(monthly_values,87)
   if monthly_quality["passed"]:
    out.append({"id":"usgs_monthly_counts:"+belt["id"],"source":"usgs","source_name":"USGS ComCat","name":belt["name"]+" monthly event counts","cohort":"seismic_monthly_counts","domain":"seismic","frequency":"monthly","axis":monthly_axis,"values":monthly_values,"sha256":hash_file(csvpath),"points":len(rows),"quality":monthly_quality})
   else:
    m["rejected"].append({"source":"usgs","series":belt["id"]+":monthly_counts","quality":monthly_quality})
   if len(rows)<SEISMIC_MIN+1:
    m["rejected"].append({"source":"usgs","series":belt["id"],"quality":{"passed":False,"reason":"fewer_than_88_events_for_87_intervals","event_count":len(rows)}});continue
   times=[datetime.fromisoformat(x["time"]) for x in rows]
   gaps=[(times[i]-times[i-1]).total_seconds()/86400 for i in range(1,len(times))]
   values=[math.log1p(x) for x in gaps]
   quality=g0(values,SEISMIC_MIN)
   if not quality["passed"]:
    m["rejected"].append({"source":"usgs","series":belt["id"],"quality":quality});continue
   out.append({"id":"usgs:"+belt["id"],"source":"usgs","source_name":"USGS ComCat","name":belt["name"],"cohort":"seismic_event_interarrival","domain":"seismic","frequency":"event_interarrival","axis":[x.isoformat() for x in times[1:]],"values":values,"sha256":hash_file(csvpath),"points":len(rows),"quality":quality})
  except Exception as exc:
   m["errors"].append({"provider":"USGS ComCat","belt":belt["id"],"error":str(exc),"time":stamp()})
   print("USGS ERROR",belt["id"],type(exc).__name__,str(exc))
 return out
def stationary_sample(x,rng,block):
 x=np.asarray(x,float);n=len(x);idx=np.empty(n,dtype=int);idx[0]=int(rng.integers(n));p=1/max(1,block)
 for i in range(1,n):idx[i]=int(rng.integers(n)) if rng.random()<p else (idx[i-1]+1)%n
 return x[idx]
def wilson(k,n):
 if not n:return None
 z=1.959963984540054;p=k/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/d
 return [max(0,c-h),min(1,c+h)]
def run_modes(x):
 out={}
 for mode in BreakDetectorV1.MODES:
  r=BreakDetectorV1(mode=mode,markov_threshold=H).analyze(x);ev=r.get("structural_breaks",[])
  out[mode]={"alarm_count":len(ev),"provisional_count":len(r.get("provisional_events",[])),"confirmed_count":len(r.get("confirmed_events",[])),"transient_count":len(r.get("transient_anomalies",[])),"unresolved_count":len(r.get("unresolved_alerts",[])),"pending_lifecycle":r.get("pending_lifecycle"),"diagnostics":r.get("diagnostics",{}),"sample_adequacy":r.get("sample_adequacy",{}),"events":ev}
 return out
def boot(x,seed,block,g1_result,domain=None,series_representation="level"):
 """Estimate a conditional null without re-integrating input returns/differences."""
 if series_representation not in {"level", "returns", "differences"}:
  raise ValueError(f"unsupported_series_representation:{series_representation}")
 x=np.asarray(x,dtype=float)
 r={k:{"alarms":0,"events":0,"runs":0,"errors":0,"alarm_probability":None,"wilson95":None} for k in BreakDetectorV1.MODES}
 seed_hash=hashlib.sha256(seed.encode()).hexdigest()
 if domain=="seismic":
  return {
   "status":"SKIPPED_DOMAIN_NULL_REQUIRED",
   "method":None,
   "null_family":None,
   "null_eligibility":SEISMIC_NULL_POLICY.split(";",1)[0].strip(),
   "alternative_null_status":"CONTRACT_ONLY_NOT_VALIDATED",
   "seismic_null_policy":SEISMIC_NULL_POLICY,
   "replicates":0,
   "mean_block_length":block,
   "by_mode":r,
   "seed_sha256":seed_hash,
   "level_screen":g1_result,
   "first_difference_screen":None,
   "series_representation":series_representation,
   "skip_reason":"GENERIC_STATIONARY_BOOTSTRAP_IS_NOT_A_SEISMIC_POINT_PROCESS_NULL",
   "note":"The detector still runs on the observed series. Seismic null calibration requires catalog completeness, declustering assessment and a fitted point-process model."
  }
 use_integrated=False
 difference_screen=None
 if g1_result.get("passed"):
  null_family=LEVEL_NULL_FAMILY
  eligibility="PRELIMINARY_LEVEL_STATIONARITY_SCREEN_PASS"
 elif (domain in INTEGRATED_NULL_DOMAINS and series_representation=="level"
       and len(x)>=STATIONARITY_MIN_OBSERVATIONS+1):
  difference_screen=g1(
   np.diff(x),
   adf_significance=INTEGRATED_ADF_SIGNIFICANCE,
   kpss_significance=INTEGRATED_KPSS_SIGNIFICANCE
  )
  if difference_screen.get("passed"):
   use_integrated=True
   null_family=INTEGRATED_NULL_FAMILY
   eligibility="PRELIMINARY_FIRST_DIFFERENCE_STATIONARITY_SCREEN_PASS"
  else:
   return {
    "status":"SKIPPED_NO_VALIDATED_NULL",
    "method":"Politis-Romano stationary bootstrap not eligible",
    "null_family":None,
    "null_eligibility":"NO_PRELIMINARY_STATIONARY_LEVEL_OR_INCREMENT_NULL",
    "alternative_null_status":"NOT_ESTABLISHED",
    "replicates":0,
    "mean_block_length":block,
    "by_mode":r,
    "seed_sha256":seed_hash,
    "level_screen":g1_result,
    "first_difference_screen":difference_screen,
    "skip_reason":"LEVEL_AND_FIRST_DIFFERENCE_SCREENS_FAILED",
    "note":"No generic fallback is applied when neither levels nor first differences pass the preliminary screen."
   }
 else:
  return {
   "status":"SKIPPED_G1_SCREEN_FAILED",
   "method":"Politis-Romano stationary bootstrap not eligible",
   "null_family":None,
   "null_eligibility":"INCREMENT_SERIES_FAILED_ITS_OWN_NULL_SCREEN" if series_representation in {"returns", "differences"} else "NO_VALIDATED_NULL_FOR_THIS_SERIES",
   "alternative_null_status":"NOT_ESTABLISHED",
   "replicates":0,
   "mean_block_length":block,
   "by_mode":r,
   "seed_sha256":seed_hash,
   "level_screen":g1_result,
   "first_difference_screen":difference_screen,
   "series_representation":series_representation,
   "skip_reason":"ALREADY_INCREMENT_SERIES_NOT_ELIGIBLE_FOR_REINTEGRATION" if series_representation in {"returns", "differences"} else g1_result.get("status","G1_NOT_PASSED"),
   "note":"Detector execution is independent of null eligibility; no valid null is established for this representation."
  }
 rng=np.random.default_rng(int(seed_hash[:16],16))
 for _ in range(REPS):
  if use_integrated:
   sampled_differences=stationary_sample(np.diff(x),rng,block)
   sample=np.concatenate(([x[0]],x[0]+np.cumsum(sampled_differences)))
  else:
   sample=stationary_sample(x,rng,block)
  for mode in BreakDetectorV1.MODES:
   try:
    z=BreakDetectorV1(mode=mode,markov_threshold=H).analyze(sample)
    ev=z.get("structural_breaks",[])
    r[mode]["runs"]+=1
    r[mode]["alarms"]+=int(bool(ev))
    r[mode]["events"]+=len(ev)
   except Exception:
    r[mode]["errors"]+=1
 for v in r.values():
  v["alarm_probability"]=v["alarms"]/v["runs"] if v["runs"] else None
  v["wilson95"]=wilson(v["alarms"],v["runs"])
 method="Integrated stationary bootstrap of first differences" if use_integrated else "Politis-Romano stationary bootstrap of levels"
 return {
  "status":"ESTIMATED_CONDITIONAL_DIAGNOSTIC",
  "method":method,
  "null_family":null_family,
  "null_eligibility":eligibility,
  "alternative_null_status":"ESTIMATED_CONDITIONALLY" if use_integrated else "NOT_REQUIRED",
  "replicates":REPS,
  "mean_block_length":block,
  "by_mode":r,
  "seed_sha256":seed_hash,
  "level_screen":g1_result,
  "first_difference_screen":difference_screen,
  "series_representation":series_representation,
  "note":"Conditional null diagnostic only; ADF/KPSS screening does not prove model adequacy and alarm probability is not an operational FPR."
 }

def series_category(item):
 if item["domain"]=="macro":return "macro"
 name=item["name"].casefold()
 energy=("crude oil","brent","wti","dubai","coal","natural gas","liquefied natural gas","lng","gasoline","diesel","heating oil","fuel oil","kerosene","propane")
 metals=("aluminum","aluminium","copper","iron ore","lead","nickel","tin","zinc","steel","gold","silver","platinum","palladium")
 agriculture=("wheat","rice","maize","corn","soy","soya","soybean","sugar","coffee","cocoa","tea","palm oil","copra","coconut","cotton","meat","beef","chicken","poultry","banana","orange","shrimp","fishmeal","sunflower","rapeseed","vegetable oil","fertilizer","phosphate","potash","urea","dap")
 if any(term in name for term in energy):return "energy"
 if any(term in name for term in metals):return "metals"
 if any(term in name for term in agriculture):return "agriculture_food"
 return "other_commodity"
def shock_eval(item,events,contract):
 axis=item["axis"];category=series_category(item)
 eligible={t["id"] for t in contract["events"] if category in t.get("applicable_categories",[])}
 candidates=[]
 for anchor_index,target in enumerate(contract["events"]):
  if target["id"] not in eligible:continue
  target_month=month(target["anchor_date"][:7])
  for event_index,event in enumerate(events):
   if event.get("detection_time") is None:continue
   try:index=int(event["detection_time"])
   except (TypeError,ValueError):continue
   if not 0<=index<len(axis):continue
   observed_month=month(axis[index])
   if observed_month is None:continue
   lead=target_month-observed_month
   if abs(lead)<=contract["matching_window_months"]:
    candidates.append((abs(lead),anchor_index,event_index,index,lead,event))
 candidates.sort(key=lambda value:(value[0],value[1],value[2]))
 used_anchors=set();used_events=set();matches={}
 for _,anchor_index,event_index,index,lead,event in candidates:
  if anchor_index in used_anchors or event_index in used_events:continue
  used_anchors.add(anchor_index);used_events.add(event_index)
  target=contract["events"][anchor_index]
  matches[target["id"]]={"event_id":target["id"],"eligible":True,"matched":True,"detection_index":index,"detected_month":axis[index],"lead_months":int(lead),"classification":"pre_anchor_signal" if lead>0 else ("same_month_detection" if lead==0 else "post_anchor_detection"),"detector_status":event.get("status")}
 found=[]
 for target in contract["events"]:
  if target["id"] in matches:found.append(matches[target["id"]])
  else:found.append({"event_id":target["id"],"eligible":target["id"] in eligible,"matched":False,"series_category":category})
 return found

def applicable_shock_series(item,contract):
 if item["frequency"]!="monthly" or item["source"]=="usgs":return False
 category=series_category(item)
 return any(category in target.get("applicable_categories",[]) for target in contract["events"])
def eval_series(item,contract):
 modes=run_modes(item["values"])
 g1_result=g1(item["values"])
 if item["frequency"]=="monthly":
  duration=max(1,len(item["values"])/12)
 else:
  times=[datetime.fromisoformat(v) for v in item["axis"]]
  duration=max(1e-9,(times[-1]-times[0]).total_seconds()/(86400*365.2425))
 for mode,v in modes.items():
  v["alarms_per_decade"]=v["alarm_count"]/duration*10
  v["shock_matching_applicable"]=applicable_shock_series(item,contract)
  v["shock_matches"]=shock_eval(item,v["events"],contract) if item["frequency"]=="monthly" and item["source"]!="usgs" else []
  matched_indices={int(match["detection_index"]) for match in v["shock_matches"] if match.get("matched") and match.get("detection_index") is not None}
  v["matched_shock_alarm_count"]=len(matched_indices)
  if v["shock_matching_applicable"]:
   v["unassociated_structural_alarm_count"]=max(0,int(v["alarm_count"])-len(matched_indices))
   v["unassociated_structural_alarms_per_decade"]=v["unassociated_structural_alarm_count"]/duration*10
  else:
   v["unassociated_structural_alarm_count"]=None
   v["unassociated_structural_alarms_per_decade"]=None
 block=MONTH_BLOCK if item["frequency"]=="monthly" else EVENT_BLOCK
 series_representation = item.get(
  "representation",
  "returns" if item["source"] in {"pink_sheet", "gem"} else "level"
 )
 if series_representation not in {"level", "returns", "differences"}:
  raise ValueError(f"unsupported_series_representation:{series_representation}")
 bootstrap_result=boot(
  item["values"],item["id"]+str(item["sha256"]),block,g1_result,
  item["domain"],series_representation=series_representation
 )
 return {
  "id":item["id"],"source":item["source"],"name":item["name"],"cohort":item["cohort"],"domain":item["domain"],"frequency":item["frequency"],"observations":len(item["values"]),"duration_years":duration,"first":item["axis"][0],"last":item["axis"][-1],"sha256":item["sha256"],"quality":item["quality"],
  "g1":g1_result,
  "evaluation_policy":{
   "detector_execution":"COMPLETED_BEFORE_NULL_SELECTION",
   "detector_execution_requires_stationarity":STATIONARITY_CONFIG["detector_execution_requires_stationarity"],
   "stationary_level_screen_passed":bool(g1_result.get("passed")),
   "bootstrap_null_status":bootstrap_result.get("status"),
   "alternative_null_status":bootstrap_result.get("alternative_null_status"),
   "interpretation":"A failed null-eligibility screen never suppresses observed-series detector execution."
  },
  "detector":modes,
  "bootstrap":bootstrap_result
 }
def normalized_csv(items):
 p=DERIVED/"normalized_detector_inputs.csv";p.parent.mkdir(parents=True,exist_ok=True)
 with p.open("w",newline="",encoding="utf-8") as f:
  w=csv.writer(f);w.writerow(["series_id","source","cohort","index","time","value","source_sha256"])
  for x in items:
   for i,(t,v) in enumerate(zip(x["axis"],x["values"])):w.writerow([x["id"],x["source"],x["cohort"],i,t,("" if x["source"]=="pink_sheet" else format(float(v),".17g")),x["sha256"]])
 return {"path":str(p.relative_to(ROOT)),"sha256":hash_file(p),"rows":sum(len(x["values"]) for x in items)}
def aggregate(results,contract):
 out={"shocks":{},"by_cohort":{}}
 for target in contract["events"]:
  out["shocks"][target["id"]]={}
  for mode in BreakDetectorV1.MODES:
   evaluations=[event for series in results for event in series["detector"][mode]["shock_matches"] if event["event_id"]==target["id"] and event.get("eligible")]
   matched=[event for event in evaluations if event["matched"]]
   pre=sum(event["lead_months"]>0 for event in matched)
   out["shocks"][target["id"]][mode]={"eligible_series":len(evaluations),"matches":len(matched),"capture_rate":len(matched)/len(evaluations) if evaluations else None,"capture_rate_pct":100*len(matched)/len(evaluations) if evaluations else None,"pre_anchor":pre,"pre_anchor_rate_pct":100*pre/len(evaluations) if evaluations else None,"same_month":sum(event["lead_months"]==0 for event in matched),"post_anchor":sum(event["lead_months"]<0 for event in matched),"median_lead":float(np.median([event["lead_months"] for event in matched])) if matched else None,"series_matches":matched}
 for cohort in sorted({series["cohort"] for series in results}):
  cohort_subset=[series for series in results if series["cohort"]==cohort]
  cohort_stats={"series_total":len(cohort_subset),"by_representation":{}}
  for representation in sorted({
   series.get("bootstrap",{}).get("series_representation",series.get("representation","unspecified"))
   for series in cohort_subset
  }):
   subset=[
    series for series in cohort_subset
    if series.get("bootstrap",{}).get("series_representation",series.get("representation","unspecified"))==representation
   ]
   representation_stats={}
   for mode in BreakDetectorV1.MODES:
    alarms=0;years=0.0;unassociated=0;matched_years=0.0;matched_series=0
    conditional_probabilities=[]
    total_replicates=0
    for series in subset:
     alarms+=series["detector"][mode]["alarm_count"]
     years+=series["duration_years"]
     boot=series["bootstrap"]["by_mode"][mode]
     runs=int(boot.get("runs",0));total_replicates+=runs
     if runs>0:
      conditional_probabilities.append(float(boot["alarms"])/runs)
     unassociated_count=series["detector"][mode]["unassociated_structural_alarm_count"]
     if unassociated_count is not None:
      unassociated+=unassociated_count
      matched_years+=series["duration_years"]
      matched_series+=1
    probs=np.asarray(conditional_probabilities,dtype=float)
    representation_stats[mode]={
     "series":len(subset),
     "g1_passed_series":sum(1 for series in subset if series["g1"].get("passed")),
     "alarms":alarms,
     "alarms_per_decade":alarms/years*10 if years else None,
     "shock_matched_cohort_series":matched_series,
     "unassociated_structural_alarms":unassociated if matched_series else None,
     "unassociated_structural_alarms_per_decade":unassociated/matched_years*10 if matched_years else None,
     "bootstrap_eligible_series":int(probs.size),
     "bootstrap_replicates_total":total_replicates,
     "conditional_bootstrap_alarm_probability_mean":float(np.mean(probs)) if probs.size else None,
     "conditional_bootstrap_alarm_probability_median":float(np.median(probs)) if probs.size else None,
     "conditional_bootstrap_alarm_probability_q25":float(np.quantile(probs,0.25)) if probs.size else None,
     "conditional_bootstrap_alarm_probability_q75":float(np.quantile(probs,0.75)) if probs.size else None,
     "conditional_bootstrap_alarm_probability_min":float(np.min(probs)) if probs.size else None,
     "conditional_bootstrap_alarm_probability_max":float(np.max(probs)) if probs.size else None
    }
   cohort_stats["by_representation"][representation]=representation_stats
  out["by_cohort"][cohort]=cohort_stats
 return out

def make_report(m):
 z=m.get("aggregate",{})
 lines=[
  "# تقرير اختبار الضغط التاريخي — CHAOS P2.2.1",
  "",
  "> تصحيح التجميع: احتمالات الإنذار في Stationary Bootstrap معروضة لكل فوج على حدة، وليست FPR مثبتة بحقيقة أرضية. لا تجمع أفواج السلع والزلازل في مقياس واحد. راجع [التدقيق الإحصائي](docs/P2.2_STATISTICAL_AUDIT_AR.md).",
  "",
  f"وقت التشغيل UTC: {m.get('run_timestamp_utc','—')}",
  f"Commit المصدر: {m.get('git_commit','—')}",
  f"الفرع: {m.get('branch','—')}",
  "الكاشف المجمد: BreakDetectorV1؛ لم تتغير معادلاته أو ثوابته.",
  "",
  "## 1. ملخص الجلب والتأهيل",
  "",
  f"- سلاسل Pink Sheet الطويلة (>500 عائد شهري): {m.get('pink_eligible',0)}.",
  f"- سلاسل GEM الشهرية الثانوية (≥87 مشاهدة): {m.get('gem_eligible',0)}.",
  f"- أحزمة USGS المستعلم عنها: {len(m.get('belts',[]))}/5؛ سلاسل الزلازل المؤهلة: {m.get('seismic_eligible',0)}.",
  f"- إجمالي السلاسل التي وصلت إلى الكاشف: {len(m.get('series_results',[]))}.",
  f"- اجتازت G1 (ADF وKPSS): {sum(1 for s in m.get('series_results',[]) if s.get('g1',{}).get('passed'))}.",
  f"- اجتازت G1 للمستوى: {sum(1 for s in m.get('series_results',[]) if s.get('g1',{}).get('passed'))}.",
  f"- استخدمت null للفروق الأولى: {sum(1 for s in m.get('series_results',[]) if s.get('bootstrap',{}).get('null_family')=='INTEGRATED_STATIONARY_BOOTSTRAP_OF_FIRST_DIFFERENCES')}.",
  f"- لم يتوفر لها null مؤهل: {sum(1 for s in m.get('series_results',[]) if not s.get('bootstrap',{}).get('replicates'))}.",
  f"- السلاسل المستبعدة: {len(m.get('rejected',[]))}؛ أخطاء المصادر: {len(m.get('errors',[]))}.",
  "",
  "## 2. G0 وG1 ومنهج Bootstrap",
  "",
  f"- G0: عدد النقاط وفق الفوج، تسلسل زمني متصل بلا ملء للفجوات، قيم منتهية، وMAD غير متدهور في نافذة الأساس الأولى.",
  f"- Pink Sheet: يتطلب 501 عائد شهري على الأقل، أي 502 سعراً موجباً متصلاً على الأقل.",
  f"- GEM وفواصل USGS: يتطلب كل فوج ثانوي 87 مشاهدة/فاصلاً على الأقل.",
  "- G1: ADF يرفض جذر الوحدة (p < 0.05) وKPSS لا يرفض استقرار المستوى (p ≥ 0.05). هذا فحص أولي مزدوج وليس برهاناً على الاستقرارية الصارمة.",
  f"- السلاسل التي تمثل مستويات: {REPS} إعادة توليد عند اجتياز G1 للمستوى؛ وإذا فشل، يُختبر G1 على الفروق الأولى ويُستخدم integrated bootstrap فقط عند نجاحه. أما Pink Sheet وGEM فهما عوائد شهرية جاهزة؛ لا يعاد أخذ فرقها ولا تكاملها. متوسط طول الكتلة الشهري {MONTH_BLOCK} شهراً.",
  "- فشل فحص المستوى والفروق الأولى يترك null غير محسوم؛ لا يُنتج احتمال إنذار بديل مصطنع.",
  "- فحص أهلية null لا يوقف تشغيل الكاشف على السلسلة المرصودة؛ يسجل كل منهما مستقلاً في manifest.",
  "- التعرض الزلزالي لا يستخدم Stationary Bootstrap عاماً؛ يتطلب point-process null مع اكتمال الكتالوج وdeclustering وملاءمة النموذج قبل أي معايرة.",
  "",
  "## 3. الإنذارات حسب الفوج — دون تجميع أفواج غير متجانسة",
  "",
  "| الفوج | تمثيل السلسلة | الوضع | السلاسل | null مؤهل | الإنذارات البنيوية | إنذارات/عقد | متوسط احتمال الإنذار الشرطي | الوسيط | Q1–Q3 |",
  "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
 ]
 for cohort,cohort_data in z.get("by_cohort",{}).items():
  for representation,by_mode in cohort_data.get("by_representation",{}).items():
   for mode,label in (("fast","Fast"),("markov_cusum","Markov"),("consensus","Consensus")):
    x=by_mode[mode]
    rate=f"{x['alarms_per_decade']:.4f}" if x.get("alarms_per_decade") is not None else "—"
    mean=x.get("conditional_bootstrap_alarm_probability_mean")
    median=x.get("conditional_bootstrap_alarm_probability_median")
    q25=x.get("conditional_bootstrap_alarm_probability_q25")
    q75=x.get("conditional_bootstrap_alarm_probability_q75")
    mean_s=f"{mean*100:.2f}%" if mean is not None else "—"
    median_s=f"{median*100:.2f}%" if median is not None else "—"
    quartile_s=f"{q25*100:.2f}–{q75*100:.2f}%" if q25 is not None and q75 is not None else "—"
    lines.append(f"| {cohort} | {representation} | {label} | {x['series']} | {x.get('bootstrap_eligible_series',0)} | {x['alarms']} | {rate} | {mean_s} | {median_s} | {quartile_s} |")
 lines += [
  "",
  "احتمال الإنذار الشرطي هو نسبة إعادات Stationary Bootstrap للسلسلة نفسها التي أصدرت إنذاراً واحداً أو أكثر، بعد اجتياز فحص G1. يعرض المتوسط والوسيط والربيعان عبر السلاسل داخل الفوج نفسه؛ ولا تجمع الأفواج في معدل واحد. هذه الكمية ليست FPR مثبتة بحقيقة أرضية معروفة، كما أن فحص ADF/KPSS لا يثبت وحده ملاءمة نموذج العدم.",
  "",
  "الفوج الزلزالي اجتاز فيه G1 سلسلة واحدة فقط من أصل خمس في كل تمثيل؛ لذلك تبقى نتائجه وصفية خاصة بسلسلة واحدة، ولا تعمم على الأحزمة الخمسة. يتطلب تفسير إنذارات الزلازل نموذج عدم من نوع point-process وتحليلاً لاكتمال الكتالوج والتجميع الزلزالي.",
  "",
  "## 4. تشخيص سلاسل GEM",
  "",
  "| المؤشر | الحالة | سجلات شهرية | سلاسل البلدان | المقبولة |",
  "|---|---|---:|---:|---:|"
 ]
 for item in m.get("gem_indicators",[]):
  lines.append(f"| {item.get('code','—')} | {item.get('status','—')} | {item.get('records_with_monthly_dates',0)} | {item.get('country_series',0)} | {item.get('accepted',0)} |")
 if not m.get("gem_indicators"):
  lines.append("| — | لم تُنتج بيانات مؤشر | 0 | 0 | 0 |")
 for error in m.get("errors",[]):
  if error.get("provider")=="World Bank GEM":
   lines.append(f"- خطأ GEM {error.get('indicator','')}: {error.get('error','')}")
 lines += [
  "",
  "## 5. مطابقة مراسي الصدمات التاريخية",
  "",
  "المراسي الأربع محددة قبل تشغيل الكاشف. المطابقة فئوية وواحد لواحد ضمن ±12 شهراً، وتستخدم وقت الكشف الفعلي. المهلة الموجبة تعني أن الإشارة سبقت المرساة، والسالبة تعني كشفاً لاحقاً لا إنذاراً مبكراً.",
  "",
  "| المرساة | الوضع | السلاسل المؤهلة | المطابقات | نسبة الالتقاط | قبل المرساة | نسبة السابق | نفس الشهر | بعد المرساة | وسيط lead (شهر) |",
  "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"
 ]
 for event_id,by in z.get("shocks",{}).items():
  for mode,label in (("fast","Fast"),("markov_cusum","Markov"),("consensus","Consensus")):
   x=by[mode]
   capture=f"{x['capture_rate_pct']:.1f}%" if x.get("capture_rate_pct") is not None else "—"
   pre_rate=f"{x['pre_anchor_rate_pct']:.1f}%" if x.get("pre_anchor_rate_pct") is not None else "—"
   median=f"{x['median_lead']:.2f}" if x.get("median_lead") is not None else "—"
   lines.append(f"| {event_id} | {label} | {x['eligible_series']} | {x['matches']} | {capture} | {x['pre_anchor']} | {pre_rate} | {x['same_month']} | {x['post_anchor']} | {median} |")
 lines += [
  "",
  "هذه المراسي تواريخ سياقية عامة وليست ادعاءً بأن كل سلعة أو سلسلة تعرضت لصدمة في اليوم نفسه. المطابقة الزمنية لا تثبت السببية ولا تثبت أن الإشارة كانت متاحة في الزمن الحقيقي عند وقوع الحدث.",
  "",
  "## 6. أحزمة USGS",
  "",
  "| الحزام | الأحداث | أول حدث UTC | آخر حدث UTC |",
  "|---|---:|---|---|"
 ]
 for belt in m.get("belts",[]):
  lines.append(f"| {belt['name']} | {belt['events']} | {belt.get('start') or '—'} | {belt.get('end') or '—'} |")
 lines += [
  "",
  "تُفحص أحزمة USGS بتمثيل الفواصل الزمنية بين الأحداث بالأيام، وبتمثيل العد الشهري الثانوي. معدل الإنذار لكل عقد لسلاسل الفواصل يستخدم المدة الفعلية بين أول وآخر حدث. النوافذ الجغرافية مربعات استعلام تقريبية وليست حدوداً تكتونية دقيقة.",
  "",
  "## 7. حدود الاستنتاج",
  "",
  "1. CONFIRMED حكم داخلي وفق قواعد الكاشف، وليس تحققاً مستقلاً من صدمة اقتصادية أو تحول جيولوجي.",
  "2. Detection Delay بعد بدء الصدمة مختلف عن Warning Lead قبل الصدمة؛ لا يجوز عرض الكشف اللاحق على أنه إنذار مبكر.",
  "3. البيانات التاريخية المنقحة حالياً لا تثبت أن القيم ذاتها كانت متاحة للمستخدم في تاريخ الحدث؛ ذلك يتطلب نسخ point-in-time.",
  "4. لا ينتج هذا التشغيل نموذج احتمال أو إنذاراً تشغيلياً أو توقعاً زلزالياً.",
  "5. سجل الصدمات محدود بأربعة مراسٍ عامة؛ الإنذارات غير المرتبطة بهذه المراسي لا تُصنف آلياً كإنذارات كاذبة.",
  "6. تغطية GEM المعلنة 1990–2023 تضعه في الفوج الثانوي ≥87 نقطة، وليس فوج Pink Sheet الصارم >500 نقطة.",
  "7. لم تُعدّل ملفات experiments أو معادلات BreakDetectorV1 المجمدة.",
  "",
  "## 8. أخطاء المصادر والاستبعادات"
 ]
 for error in m.get("errors",[]):
  lines.append(f"- {error.get('provider','مصدر غير محدد')} {error.get('indicator',error.get('belt',''))}: {error.get('error','خطأ غير موصوف')}")
 if not m.get("errors"):
  lines.append("- لا توجد أخطاء مصادر مسجلة.")
 lines += ["",f"- عدد السلاسل المستبعدة: {len(m.get('rejected',[]))}"]
 lines += ["","## 9. سجل التدقيق",f"- Manifest: {m.get('manifest_path','—')}",f"- Normalized inputs: {m.get('normalized',{}).get('path','—')} SHA-256 {m.get('normalized',{}).get('sha256','—')}",f"- Dependency inventory: {m.get('dependencies_path','—')}",f"- Checksums: {m.get('checksums_path','—')}","- Raw source responses: ضمن GitHub Actions Artifact. Pink Sheet يبقى في الذاكرة فقط ما دامت شروط إعادة توزيع ملف XLSX غير محسومة.","",f"حالة التشغيل: {m.get('run_status','—')}",""]
 return "\n".join(lines)


def main():
 for path in (RAW,DERIVED,OUT):
  path.mkdir(parents=True,exist_ok=True)
 contract=json.loads((HERE/"shock_event_contract.json").read_text(encoding="utf-8"))
 dependencies=dependency_inventory()
 DEPENDENCIES.write_text(json.dumps(dependencies,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 m={
  "version":"1.7","pipeline_config":PIPELINE_CONFIG,"gem_config":GEM_CONFIG,"seismic_config":SEISMIC_CONFIG,
  "observation_time_support":TIME_SUPPORT_REGISTRY,
  "run_timestamp_utc":stamp(),
  "git_commit":os.getenv("GITHUB_SHA","local-unresolved"),
  "branch":os.getenv("GITHUB_REF_NAME","local"),
  "detector":"isolated_break_detector_v1",
  "markov_H":H,
  "period":f"{Y0}-01/{Y1}-12",
  "stationarity_screen":{
   "method":"ADF plus KPSS preliminary screens",
   "scope":"null eligibility only; observed-series detector execution is independent",
   "minimum_observations":STATIONARITY_MIN_OBSERVATIONS,
   "adf_significance":STATIONARITY_ADF_SIGNIFICANCE,
   "kpss_significance":STATIONARITY_KPSS_SIGNIFICANCE,
   "integrated_adf_significance":INTEGRATED_ADF_SIGNIFICANCE,
   "integrated_kpss_significance":INTEGRATED_KPSS_SIGNIFICANCE,
   "level_null_family":LEVEL_NULL_FAMILY,
   "integrated_null_family":INTEGRATED_NULL_FAMILY,
   "integrated_null_domains":sorted(INTEGRATED_NULL_DOMAINS),
   "seismic_null_policy":SEISMIC_NULL_POLICY
  },
  "dependencies":dependencies,
  "bootstrap":{
   "method":"domain-routed conditional null diagnostics",
   "replicates":REPS,
   "monthly_mean_block":MONTH_BLOCK,
   "event_mean_block":EVENT_BLOCK,
   "economic_null_routing":["level_stationary_bootstrap","integrated_first_difference_bootstrap","no_null_when_both_screens_fail"],
   "level_null_family":LEVEL_NULL_FAMILY,
   "integrated_null_family":INTEGRATED_NULL_FAMILY,
   "integrated_null_domains":sorted(INTEGRATED_NULL_DOMAINS),
   "seismic_null_routing":"point_process_model_required",
   "seismic_generic_bootstrap_enabled":BOOTSTRAP_CONFIG["seismic_generic_bootstrap_enabled"],
   "conditional_alarm_probability_only":BOOTSTRAP_CONFIG["conditional_alarm_probability_only"],
   "operational_fpr_claim_permitted":BOOTSTRAP_CONFIG["operational_fpr_claim_permitted"]
  },
  "shock_contract":contract,
  "sources":[],
  "gem_indicators":[],
  "belts":[],
  "errors":[],
  "rejected":[]
 }
 print("Pink Sheet")
 pink_items=pink(m)
 print("PINK ACCEPTED",len(pink_items))
 print("GEM")
 gem_items=gem(m)
 print("GEM ACCEPTED",len(gem_items))
 print("USGS belts")
 seismic_items=seismic(m)
 print("USGS ACCEPTED",len(seismic_items))
 candidates=pink_items+gem_items+seismic_items
 m["pink_eligible"]=len(pink_items)
 m["gem_eligible"]=len(gem_items)
 m["seismic_eligible"]=len(seismic_items)
 results=[]
 if pink_items and seismic_items:
  for index,item in enumerate(candidates,1):
   print(f"{index}/{len(candidates)} {item['id']} n={len(item['values'])}")
   results.append(eval_series(item,contract))
  m["normalized"]=normalized_csv(candidates)
  m["run_status"]="COMPLETED_WITH_SOURCE_WARNINGS" if m["errors"] else "COMPLETED"
 else:
  m["normalized"]={"path":"not-created","sha256":"none","rows":0}
  m["run_status"]="FAILED_REQUIRED_COHORT_MISSING"
 m["series_results"]=results
 m["aggregate"]=aggregate(results,contract)
 m["manifest_path"]=str(MANIFEST.relative_to(ROOT))
 m["checksums_path"]=str(CHECKSUMS.relative_to(ROOT))
 m["dependencies_path"]=str(DEPENDENCIES.relative_to(ROOT))
 m["raw_snapshots"]=len(m["sources"])

 sum_paths=[p for p in list(RAW.rglob("*"))+list(DERIVED.rglob("*")) if p.is_file()]
 sum_paths += [
  HERE/"run_pipeline.py",
  HERE/"shock_event_contract.json",
  HERE/"requirements.txt",
  HERE/"tests"/"test_pipeline.py",
  HERE/"config"/"pipeline.json",
  HERE/"config"/"gem_indicators.json",
  HERE/"config"/"seismic_belts.json",
  TIME_SUPPORT_SCHEMA_PATH,
  HERE/"README_AR.md",
  DEPENDENCIES,
  ROOT/".github"/"workflows"/"real-data-stress.yml",
  ROOT/"structural_engine"/"isolated_break_detector_v1"/"break_detector_v1.py",
  ROOT/"structural_engine"/"isolated_break_detector_v1"/"engine_fast_ref.py",
  ROOT/"structural_engine"/"isolated_break_detector_v1"/"engine_markov_cusum.py"
 ]
 sums=[]
 for path in sorted(set(path for path in sum_paths if path.exists())):
  sums.append(f"{hash_file(path)}  {path.relative_to(ROOT).as_posix()}")
 CHECKSUMS.write_text("\n".join(sums)+"\n",encoding="utf-8")
 MANIFEST.write_text(json.dumps(m,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 REPORT.write_text(make_report(m),encoding="utf-8")
 print("STATUS",m["run_status"],"series",len(results),"errors",len(m["errors"]),"G1_PASS",sum(1 for series in results if series["g1"].get("passed")))
 return 0 if m["run_status"] in {"COMPLETED","COMPLETED_WITH_SOURCE_WARNINGS"} else 2
if __name__=="__main__":raise SystemExit(main())
