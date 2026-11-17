"""P2.2 real-data stress pipeline. Frozen BreakDetectorV1 is imported and never edited."""
from __future__ import annotations
import csv, hashlib, json, math, os, re, time, urllib.parse, urllib.request, warnings
from collections import defaultdict, Counter
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import numpy as np
from openpyxl import load_workbook
from statsmodels.tsa.stattools import adfuller, kpss
from structural_engine.isolated_break_detector_v1 import BreakDetectorV1, DEFAULT_MARKOV_THRESHOLD

ROOT=Path(__file__).resolve().parents[1]
HERE=Path(__file__).resolve().parent
RAW=ROOT/"artifacts"/"real_data_stress"/"raw"
DERIVED=ROOT/"artifacts"/"real_data_stress"/"derived"
OUT=HERE/"results"; REPORT=ROOT/"REAL_DATA_STRESS_REPORT_AR.md"
MANIFEST=OUT/"real_data_stress_manifest.json"; CHECKSUMS=OUT/"SHA256SUMS.txt"
Y0,Y1=1980,2024
PINK_MIN=int(os.getenv("STRESS_MIN_COMMODITY_POINTS","501"))
GEM_MIN=int(os.getenv("STRESS_MIN_GEM_POINTS","87"))
SEISMIC_MIN=87
REPS=int(os.getenv("STRESS_BOOTSTRAP_REPLICATES","199"))
MONTH_BLOCK=int(os.getenv("STRESS_BOOTSTRAP_MEAN_BLOCK_MONTHS","12"))
EVENT_BLOCK=int(os.getenv("STRESS_BOOTSTRAP_MEAN_BLOCK_EVENTS","25"))
MAG=float(os.getenv("STRESS_USGS_MIN_MAGNITUDE","4.5"))
H=DEFAULT_MARKOV_THRESHOLD
UA="CHAOS-P2.2/1.0 https://github.com/uniqueteamyemen/CHAOS"
LANDING="https://www.worldbank.org/en/research/commodity-markets"
PINK_FALLBACK="https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx"
GEM={
 "CPTOTSAXN":"Consumer price index, total, seasonally adjusted",
 "IPTOTSAKD":"Industrial production, total, seasonally adjusted",
 "DXGSRMRCHSAXD":"Merchandise exports, seasonally adjusted, current US dollars",
 "DXGSRMRCHNSKD":"Merchandise exports, seasonally adjusted, constant US dollars",
}
BELTS=[
 {"id":"japan_kuril_kamchatka","name":"Japan–Kuril–Kamchatka","minlatitude":35,"maxlatitude":60,"minlongitude":140,"maxlongitude":180},
 {"id":"sunda_andaman","name":"Sunda–Andaman","minlatitude":-15,"maxlatitude":20,"minlongitude":90,"maxlongitude":130},
 {"id":"andes_subduction","name":"Andes subduction","minlatitude":-45,"maxlatitude":10,"minlongitude":-82,"maxlongitude":-65},
 {"id":"alaska_aleutian","name":"Alaska–Aleutian","minlatitude":50,"maxlatitude":65,"minlongitude":-180,"maxlongitude":-130},
 {"id":"hellenic_anatolian","name":"Hellenic–Anatolian","minlatitude":30,"maxlatitude":42,"minlongitude":18,"maxlongitude":35},
]
def stamp(): return datetime.now(timezone.utc).isoformat()
def digest(b): return hashlib.sha256(b).hexdigest()
def hash_file(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for x in iter(lambda:f.read(1024*1024),b""):h.update(x)
 return h.hexdigest()
def get(url,retries=4,timeout=90):
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
def keep_raw(rel,data,provider,url,params=None):
 p=RAW/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 return {"path":str(p.relative_to(ROOT)),"sha256":digest(data),"bytes":len(data),"provider":provider,"url":url,"parameters":params or {},"retrieved_at_utc":stamp()}
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
def g1(x):
 a=np.asarray(x,dtype=float)
 if a.ndim!=1 or not np.all(np.isfinite(a)):
  return {"passed":False,"status":"INVALID_INPUT","reason":"nonfinite_or_nonvector","observations":int(a.size)}
 if len(a)<87:
  return {"passed":False,"status":"NOT_TESTED","reason":"fewer_than_87_observations","observations":int(len(a))}
 if mad(a)<=1e-10:
  return {"passed":False,"status":"DEGENERATE","reason":"degenerate_series_mad","observations":int(len(a))}
 try:
  with warnings.catch_warnings(record=True) as caught:
   warnings.simplefilter("always")
   adf_result=adfuller(a,regression="c",autolag="AIC")
   kpss_result=kpss(a,regression="c",nlags="auto")
  adf_p=float(adf_result[1]);kpss_p=float(kpss_result[1])
  adf_ok=adf_p<0.05;kpss_ok=kpss_p>=0.05
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
   "significance":0.05,
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
  m["sources"].append({"provider":"World Bank Pink Sheet","url":url,"discovery":discovery,"sha256":sh,"bytes":len(raw),"retrieved_at_utc":stamp(),"raw_preserved":"in-memory only; workbook-specific redistribution terms not established","layout":layout,"accepted_series":len(items)})
  return items
 except Exception as e:
  m["errors"].append({"provider":"World Bank Pink Sheet","url":url,"error":str(e),"time":stamp()});return []
def gem(m):
 out=[]
 for code,desc in GEM.items():
  page=1;pages=1;groups=defaultdict(dict);names={};hashes=[]
  try:
   while page<=pages:
    q=urllib.parse.urlencode({"source":15,"format":"json","per_page":20000,"page":page,"date":"1990M01:2023M12"})
    url=f"https://api.worldbank.org/v2/country/all/indicator/{code}?{q}"
    raw=get(url,3);obj=json.loads(raw)
    if not isinstance(obj,list) or len(obj)<2 or not isinstance(obj[0],dict):raise ValueError("unexpected API response")
    pages=int(obj[0].get("pages",1));rows=obj[1]
    if not isinstance(rows,list):raise ValueError("API has no data rows")
    rec=keep_raw(f"world_bank/gem/{code}_page_{page:03d}.json",raw,"World Bank GEM",url,{"source":15,"indicator":code,"page":page})
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
   summary={"code":code,"description":desc,"date_query":"1990M01:2023M12","frequency_policy":"monthly-only by actual year-month response keys; frequency query parameter omitted because World Bank documents frequency as an MRV modifier","records_with_monthly_dates":sum(map(len,groups.values())),"country_series":len(groups),"accepted":accepted_for_code,"raw_hashes":hashes,"status":"monthly_data_found" if groups else "no_monthly_records_for_indicator"}
   m["gem_indicators"].append(summary)
   print("GEM",code,"monthly_records",summary["records_with_monthly_dates"],"country_series",summary["country_series"],"accepted",accepted_for_code)
  except Exception as e:
   error_record={"provider":"World Bank GEM","indicator":code,"error":str(e),"time":stamp()}
   m["errors"].append(error_record)
   m["gem_indicators"].append({"code":code,"description":desc,"status":"api_error","error":str(e)})
   print("GEM ERROR",code,type(e).__name__,str(e))
 return out
def usgs_query(belt,start,end,m,depth=0):
 p={"format":"geojson","starttime":start,"endtime":end,"minmagnitude":MAG,"minlatitude":belt["minlatitude"],"maxlatitude":belt["maxlatitude"],"minlongitude":belt["minlongitude"],"maxlongitude":belt["maxlongitude"],"orderby":"time-asc","limit":20000}
 url="https://earthquake.usgs.gov/fdsnws/event/1/query?"+urllib.parse.urlencode(p)
 raw=get(url,4,120);r=keep_raw(f"usgs/{belt['id']}/{start.replace(':','_')}_{end.replace(':','_')}.geojson",raw,"USGS ComCat",url,p);m["sources"].append(r)
 fs=json.loads(raw).get("features",[])
 if len(fs)>=19999:
  a=datetime.fromisoformat(start);b=datetime.fromisoformat(end)
  if (b-a).total_seconds()<86400 or depth>=12:raise RuntimeError("catalog query remains saturated at minimum interval")
  mid=(a+(b-a)/2).strftime("%Y-%m-%dT%H:%M:%S")
  return usgs_query(belt,start,mid,m,depth+1)+usgs_query(belt,mid,end,m,depth+1)
 return fs
def seismic(m):
 out=[]
 for belt in BELTS:
  try:
   fs=usgs_query(belt,f"{Y0}-01-01T00:00:00",f"{Y1+1}-01-01T00:00:00",m);events={}
   for f in fs:
    p=f.get("properties") or {};g=f.get("geometry") or {};c=g.get("coordinates") or []
    if p.get("time") is None or p.get("mag") is None or len(c)<2:continue
    eid=str(f.get("id") or f"{p['time']}:{p['mag']}:{c[0]}:{c[1]}")
    events[eid]={"id":eid,"time":datetime.fromtimestamp(p["time"]/1000,tz=timezone.utc).isoformat(),"epoch_ms":int(p["time"]),"magnitude":float(p["mag"]),"longitude":c[0],"latitude":c[1],"depth_km":c[2] if len(c)>2 else None,"place":p.get("place")}
   rows=sorted(events.values(),key=lambda x:x["epoch_ms"])
   csvpath=DERIVED/f"{belt['id']}_events.csv";csvpath.parent.mkdir(parents=True,exist_ok=True)
   cols=["id","time","epoch_ms","magnitude","longitude","latitude","depth_km","place"]
   with csvpath.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)
   rec={"id":belt["id"],"name":belt["name"],"bbox":{k:belt[k] for k in ("minlatitude","maxlatitude","minlongitude","maxlongitude")},"min_magnitude":MAG,"events":len(rows),"start":rows[0]["time"] if rows else None,"end":rows[-1]["time"] if rows else None,"csv_sha256":hash_file(csvpath)}
   m["belts"].append(rec)
   # Secondary monthly event-count representation; empty months are zero only
   # inside the fully queried USGS catalog window.
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
   vals=[math.log1p(x) for x in gaps];q=g0(vals,SEISMIC_MIN)
   if not q["passed"]:
    m["rejected"].append({"source":"usgs","series":belt["id"],"quality":q});continue
   out.append({"id":"usgs:"+belt["id"],"source":"usgs","source_name":"USGS ComCat","name":belt["name"],"cohort":"seismic_event_interarrival","domain":"seismic","frequency":"event_interarrival","axis":[x.isoformat() for x in times[1:]],"values":vals,"sha256":hash_file(csvpath),"points":len(rows),"quality":q})
  except Exception as e:
   m["errors"].append({"provider":"USGS ComCat","belt":belt["id"],"error":str(e),"time":stamp()})
   print("USGS ERROR",belt["id"],type(e).__name__,str(e))
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
def boot(x,seed,block,g1_result):
 r={k:{"alarms":0,"events":0,"runs":0,"errors":0,"fpr":None,"wilson95":None} for k in BreakDetectorV1.MODES}
 if not g1_result.get("passed"):
  return {"status":"SKIPPED_G1_SCREEN_FAILED","method":"Politis-Romano stationary bootstrap","replicates":0,"mean_block_length":block,"by_mode":r,"seed_sha256":hashlib.sha256(seed.encode()).hexdigest(),"skip_reason":g1_result.get("status","G1_NOT_PASSED"),"note":"Stationary block resampling is not run unless the ADF/KPSS screen passes."}
 rng=np.random.default_rng(int(hashlib.sha256(seed.encode()).hexdigest()[:16],16))
 for _ in range(REPS):
  s=stationary_sample(x,rng,block)
  for mode in BreakDetectorV1.MODES:
   try:
    z=BreakDetectorV1(mode=mode,markov_threshold=H).analyze(s);ev=z.get("structural_breaks",[]);r[mode]["runs"]+=1;r[mode]["alarms"]+=int(bool(ev));r[mode]["events"]+=len(ev)
   except Exception:r[mode]["errors"]+=1
 for v in r.values():
  v["fpr"]=v["alarms"]/v["runs"] if v["runs"] else None;v["wilson95"]=wilson(v["alarms"],v["runs"])
 return {"method":"Politis-Romano stationary bootstrap","replicates":REPS,"mean_block_length":block,"by_mode":r,"seed_sha256":hashlib.sha256(seed.encode()).hexdigest(),"note":"Conditional resampling diagnostic; stationarity and domain-specific null assumptions require separate validation."}
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
  shock_applicable=item["frequency"]=="monthly" and item["source"]!="usgs"
  v["shock_matching_applicable"]=shock_applicable
  v["shock_matches"]=shock_eval(item,v["events"],contract) if shock_applicable else []
  matched_indices={int(match["detection_index"]) for match in v["shock_matches"] if match.get("matched") and match.get("detection_index") is not None}
  v["matched_shock_alarm_count"]=len(matched_indices)
  if shock_applicable:
   v["unassociated_structural_alarm_count"]=max(0,int(v["alarm_count"])-len(matched_indices))
   v["unassociated_structural_alarms_per_decade"]=v["unassociated_structural_alarm_count"]/duration*10
  else:
   v["unassociated_structural_alarm_count"]=None
   v["unassociated_structural_alarms_per_decade"]=None
 block=MONTH_BLOCK if item["frequency"]=="monthly" else EVENT_BLOCK
 return {"id":item["id"],"source":item["source"],"name":item["name"],"cohort":item["cohort"],"domain":item["domain"],"frequency":item["frequency"],"observations":len(item["values"]),"duration_years":duration,"first":item["axis"][0],"last":item["axis"][-1],"sha256":item["sha256"],"quality":item["quality"],"g1":g1_result,"detector":modes,"bootstrap":boot(item["values"],item["id"]+str(item["sha256"]),block,g1_result)}
def normalized_csv(items):
 p=DERIVED/"normalized_detector_inputs.csv";p.parent.mkdir(parents=True,exist_ok=True)
 with p.open("w",newline="",encoding="utf-8") as f:
  w=csv.writer(f);w.writerow(["series_id","source","cohort","index","time","value","source_sha256"])
  for x in items:
   for i,(t,v) in enumerate(zip(x["axis"],x["values"])):w.writerow([x["id"],x["source"],x["cohort"],i,t,("" if x["source"]=="pink_sheet" else format(float(v),".17g")),x["sha256"]])
 return {"path":str(p.relative_to(ROOT)),"sha256":hash_file(p),"rows":sum(len(x["values"]) for x in items)}
def aggregate(results,contract):
 out={"by_mode":{},"shocks":{}}
 for mode in BreakDetectorV1.MODES:
  alarms=0;years=0.0;hits=0;total=0;unassociated=0;matched_years=0.0;matched_series=0
  for series in results:
   alarms+=series["detector"][mode]["alarm_count"];years+=series["duration_years"]
   bootstrap=series["bootstrap"]["by_mode"][mode];hits+=bootstrap["alarms"];total+=bootstrap["runs"]
   unassociated_count=series["detector"][mode]["unassociated_structural_alarm_count"]
   if unassociated_count is not None:
    unassociated+=unassociated_count;matched_years+=series["duration_years"];matched_series+=1
  out["by_mode"][mode]={"series":len(results),"g1_passed_series":sum(1 for series in results if series["g1"].get("passed")),"raw_alarms":alarms,"alarms_per_decade":alarms/years*10 if years else None,"shock_matched_cohort_series":matched_series,"unassociated_structural_alarms":unassociated if matched_series else None,"unassociated_structural_alarms_per_decade":unassociated/matched_years*10 if matched_years else None,"bootstrap_fpr":hits/total if total else None,"bootstrap_wilson95":wilson(hits,total),"bootstrap_alarm_replicates":hits,"bootstrap_replicates":total}
 for target in contract["events"]:
  out["shocks"][target["id"]]={}
  for mode in BreakDetectorV1.MODES:
   evaluations=[event for series in results for event in series["detector"][mode]["shock_matches"] if event["event_id"]==target["id"] and event.get("eligible")]
   matched=[event for event in evaluations if event["matched"]]
   pre=sum(event["lead_months"]>0 for event in matched)
   out["shocks"][target["id"]][mode]={"eligible_series":len(evaluations),"matches":len(matched),"capture_rate":len(matched)/len(evaluations) if evaluations else None,"capture_rate_pct":100*len(matched)/len(evaluations) if evaluations else None,"pre_anchor":pre,"pre_anchor_rate_pct":100*pre/len(evaluations) if evaluations else None,"same_month":sum(event["lead_months"]==0 for event in matched),"post_anchor":sum(event["lead_months"]<0 for event in matched),"median_lead":float(np.median([event["lead_months"] for event in matched])) if matched else None,"series_matches":matched}
 out["by_cohort"]={}
 for cohort in sorted({series["cohort"] for series in results}):
  subset=[series for series in results if series["cohort"]==cohort]
  cohort_stats={}
  for mode in BreakDetectorV1.MODES:
   alarms=0;years=0.0;hits=0;total=0;unassociated=0;matched_years=0.0;matched_series=0
   for series in subset:
    alarms+=series["detector"][mode]["alarm_count"];years+=series["duration_years"]
    boot=series["bootstrap"]["by_mode"][mode];hits+=boot["alarms"];total+=boot["runs"]
    unassociated_count=series["detector"][mode]["unassociated_structural_alarm_count"]
    if unassociated_count is not None:
     unassociated+=unassociated_count;matched_years+=series["duration_years"];matched_series+=1
   cohort_stats[mode]={"series":len(subset),"g1_passed_series":sum(1 for series in subset if series["g1"].get("passed")),"alarms":alarms,"alarms_per_decade":alarms/years*10 if years else None,"shock_matched_cohort_series":matched_series,"unassociated_structural_alarms":unassociated if matched_series else None,"unassociated_structural_alarms_per_decade":unassociated/matched_years*10 if matched_years else None,"bootstrap_fpr":hits/total if total else None,"bootstrap_wilson95":wilson(hits,total)}
  out["by_cohort"][cohort]=cohort_stats
 return out

def make_report(m):
 z=m["aggregate"]
 lines=["# تقرير اختبار الضغط التاريخي — CHAOS P2.2","",f"وقت التشغيل UTC: {m['run_timestamp_utc']}  ",f"Commit المصدر: {m['git_commit']}  ","الكاشف المجمد: BreakDetectorV1؛ لا تعديل للمعادلات أو الثوابت.","","## ملخص الجلب والتأهيل","",f"- سلاسل Pink Sheet الطويلة (>500 نقطة): {m['pink_eligible']}.",f"- سلاسل GEM الشهرية الثانوية (≥87 نقطة): {m['gem_eligible']}.",f"- أحزمة USGS المستعلم عنها: {len(m['belts'])}/5؛ سلاسل الفواصل المؤهلة: {m['seismic_eligible']}.",f"- إجمالي السلاسل المشغلة: {len(m['series_results'])}.",f"- اجتاز فحص G1 (ADF وKPSS): {sum(1 for s in m['series_results'] if s['g1'].get('passed'))}؛ تم تجاوز Bootstrap للسلاسل التي لم تجتز G1: {sum(1 for s in m['series_results'] if not s['g1'].get('passed'))}.",f"- الاستبعادات: {len(m['rejected'])}؛ أخطاء المصادر: {len(m['errors'])}.","","## معدل الإنذار مقارنة بالـ Stationary Block-Bootstrap","","| الوضع | السلاسل | G1 مؤهلة | الإنذارات المرصودة | إنذارات/عقد | غير مرتبطة بمرساة/عقد | Bootstrap FPR | Wilson 95% |","|---|---:|---:|---:|---:|---:|---:|---:|"]
 for mode,label in (("fast","Fast"),("markov_cusum","Markov CUSUM H=8.5"),("consensus","Consensus")):
  x=z["by_mode"][mode];ci=x["bootstrap_wilson95"]
  fpr=f"{x['bootstrap_fpr']*100:.2f}%" if x["bootstrap_fpr"] is not None else "—"
  ci_s=f"{ci[0]*100:.2f}–{ci[1]*100:.2f}%" if ci else "—"
  rate=f"{x['alarms_per_decade']:.4f}" if x["alarms_per_decade"] is not None else "—";unassoc=f"{x['unassociated_structural_alarms_per_decade']:.4f}" if x["unassociated_structural_alarms_per_decade"] is not None else "—";lines.append(f"| {label} | {x['series']} | {x['g1_passed_series']} | {x['raw_alarms']} | {rate} | {unassoc} | {fpr} | {ci_s} |")
 lines += ["","Bootstrap FPR هو نسبة عينات العدم المعاد توليدها التي أصدرت إنذاراً بنيوياً واحداً على الأقل، ويُحسب فقط للسلاسل التي اجتازت فحص G1. الإنذارات غير المرتبطة بمراسي الصدمات المحددة ليست بالضرورة إنذارات كاذبة علمياً؛ فقد توجد تحولات حقيقية غير مدرجة في سجل المراسي.","","### التفصيل حسب فوج البيانات","","| الفوج | الوضع | السلاسل | الإنذارات | إنذارات/عقد | Bootstrap FPR |","|---|---|---:|---:|---:|---:|"]
 for cohort,by_mode in m["aggregate"]["by_cohort"].items():
  for mode,label in (("fast","Fast"),("markov_cusum","Markov"),("consensus","Consensus")):
   x=by_mode[mode];fpr=f"{x['bootstrap_fpr']*100:.2f}%" if x["bootstrap_fpr"] is not None else "—"
   rate=f"{x['alarms_per_decade']:.4f}" if x["alarms_per_decade"] is not None else "—"
   lines.append(f"| {cohort} | {label} | {x['series']} | {x['alarms']} | {rate} | {fpr} |")
 lines += ["","## مطابقة مراسي الصدمات التاريخية","","تُحترم فئات الأحداث المثبتة مسبقاً في العقد، وتُطابق الإشارات واحداً لواحد ضمن ±12 شهراً؛ لا يمكن إعادة استخدام إنذار لمرساتين. نسبة الالتقاط هي نسبة السلاسل المؤهلة التي سجلت كشفاً داخل النافذة. نسبة ما قبل المرساة تقيس الإشارات التي سبقت التاريخ المرجعي فعلياً، ولا تعني وحدها إنذاراً تنبؤياً مستقلاً.","","| المرساة | الوضع | المؤهلة | المطابقة ±12 شهر | نسبة الالتقاط | قبل المرساة | نسبة السابق | نفس الشهر | بعد المرساة | وسيط lead |","|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
 for eid,by in z["shocks"].items():
  for mode,label in (("fast","Fast"),("markov_cusum","Markov"),("consensus","Consensus")):
   x=by[mode];cap=f"{x['capture_rate_pct']:.1f}%" if x["capture_rate_pct"] is not None else "—";pre=f"{x['pre_anchor_rate_pct']:.1f}%" if x["pre_anchor_rate_pct"] is not None else "—"
   lines.append(f"| {eid} | {label} | {x['eligible_series']} | {x['matches']} | {cap} | {x['pre_anchor']} | {pre} | {x['same_month']} | {x['post_anchor']} | {x['median_lead'] if x['median_lead'] is not None else '—'} |")
 lines += ["","المراسي تواريخ سياقية عامة وليست ادعاءً أن جميع السلع تعرضت لصدمة في التاريخ نفسه. المطابقة لا تثبت السببية.","","## أحزمة USGS","","| الحزام | الأحداث | البداية | النهاية |","|---|---:|---|---|"]
 for b in m["belts"]:lines.append(f"| {b['name']} | {b['events']} | {b['start'] or '—'} | {b['end'] or '—'} |")
 lines += ["","تُختبر أحزمة USGS بتمثيلين مستقلين: الفواصل بين الأحداث بالأيام، والعدّ الشهري الثانوي داخل نافذة الاستعلام المكتملة. معدل الإنذار لكل عقد في سلسلة الفواصل يستخدم المدة الفعلية بين أول وآخر حدث. Stationary Bootstrap للفواصل تشخيص مشروط فقط، ويجب استكماله بتحليل اكتمال الكتالوج والتجمعات ونماذج point-process.","","## حدود الاستنتاج","","1. CONFIRMED قرار داخلي للكاشف وليس تحققاً مستقلاً من صدمة تاريخية.", "2. حساب المهلة يستخدم وقت الكشف الفعلي لا estimated onset.", "3. التواريخ التاريخية المنقحة حالياً لا تثبت أن البيانات ذاتها كانت متاحة في وقت الحدث؛ الاختبار الحقيقي يتطلب نسخ point-in-time.", "4. لا ينتج هذا التشغيل نموذجاً احتمالياً أو إنذاراً تشغيلياً.", "5. ملفات experiments والكاشف المجمد لم تُعدّل.", "6. GEM حد تغطيته المعلن 1990–2023؛ لذا يُعامل كفوج ثانوي ≥87 نقطة وليس ضمن فوج Pink Sheet الصارم >500 نقطة.","","## سجل التدقيق",f"- Manifest: {m['manifest_path']}",f"- Normalized inputs: {m['normalized']['path']} SHA-256 {m['normalized']['sha256']}",f"- Checksums: {m['checksums_path']}","- Raw API payloads: مرفقة ضمن GitHub Actions Artifact؛ ملف Pink Sheet الأصلي بقي في الذاكرة ولم يُنشر لعدم حسم ترخيص إعادة توزيعه.","",f"حالة التشغيل: {m['run_status']}",""]
 return "\n".join(lines)
def main():
 for p in (RAW,DERIVED,OUT):p.mkdir(parents=True,exist_ok=True)
 contract=json.loads((HERE/"shock_event_contract.json").read_text(encoding="utf-8"))
 m={"version":"1.1","run_timestamp_utc":stamp(),"git_commit":os.getenv("GITHUB_SHA","local-unresolved"),"branch":os.getenv("GITHUB_REF_NAME","local"),"detector":"isolated_break_detector_v1","markov_H":H,"period":f"{Y0}-01/{Y1}-12","stationarity_screen":{"method":"ADF plus KPSS at 5% significance","bootstrap_policy":"run Stationary Block-Bootstrap only when ADF rejects a unit root and KPSS does not reject level stationarity"},"bootstrap":{"method":"Politis-Romano Stationary Bootstrap","replicates":REPS,"monthly_mean_block":MONTH_BLOCK,"event_mean_block":EVENT_BLOCK},"shock_contract":contract,"sources":[],"gem_indicators":[],"belts":[],"errors":[],"rejected":[]}
 print("Pink Sheet");pink_items=pink(m);print("accepted",len(pink_items))
 print("GEM");gem_items=gem(m);print("accepted",len(gem_items))
 print("USGS belts");seismic_items=seismic(m);print("accepted",len(seismic_items))
 candidates=pink_items+gem_items+seismic_items
 m["pink_eligible"]=len(pink_items);m["gem_eligible"]=len(gem_items);m["seismic_eligible"]=len(seismic_items)
 if not pink_items or not seismic_items:
  m["run_status"]="FAILED_REQUIRED_COHORT_MISSING";m["series_results"]=[];m["aggregate"]=aggregate([],contract);m["normalized"]={"path":"not-created","sha256":"none","rows":0}
  m["manifest_path"]=str(MANIFEST.relative_to(ROOT));m["checksums_path"]=str(CHECKSUMS.relative_to(ROOT));MANIFEST.write_text(json.dumps(m,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");REPORT.write_text(make_report(m),encoding="utf-8");return 2
 results=[]
 for n,item in enumerate(candidates,1):
  print(f"{n}/{len(candidates)} {item['id']} n={len(item['values'])}")
  results.append(eval_series(item,contract))
 normalized=normalized_csv(candidates);m["normalized"]=normalized;m["series_results"]=results;m["aggregate"]=aggregate(results,contract);m["run_status"]="COMPLETED_WITH_SOURCE_WARNINGS" if m["errors"] else "COMPLETED"
 sums=[]
 for p in sorted([p for p in list(RAW.rglob("*"))+list(DERIVED.rglob("*")) if p.is_file()]):sums.append(f"{hash_file(p)}  {p.relative_to(ROOT).as_posix()}")
 for p in [HERE/"run_pipeline.py",HERE/"shock_event_contract.json",ROOT/"structural_engine/isolated_break_detector_v1/break_detector_v1.py",ROOT/"structural_engine/isolated_break_detector_v1/engine_fast_ref.py",ROOT/"structural_engine/isolated_break_detector_v1/engine_markov_cusum.py"]:
  sums.append(f"{hash_file(p)}  {p.relative_to(ROOT).as_posix()}")
 CHECKSUMS.write_text("\n".join(sums)+"\n",encoding="utf-8")
 m["manifest_path"]=str(MANIFEST.relative_to(ROOT));m["checksums_path"]=str(CHECKSUMS.relative_to(ROOT));m["raw_snapshots"]=len(m["sources"])
 MANIFEST.write_text(json.dumps(m,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");REPORT.write_text(make_report(m),encoding="utf-8")
 print("STATUS",m["run_status"],"series",len(results),"errors",len(m["errors"]))
 return 0
if __name__=="__main__":raise SystemExit(main())
