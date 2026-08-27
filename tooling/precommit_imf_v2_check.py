#!/usr/bin/env python3
from pathlib import Path
import json,re,subprocess,sys
ROOT=Path('/home/ubuntu/CHAOS')
staged=subprocess.check_output(['git','diff','--cached','--name-only'],cwd=ROOT,text=True).splitlines(); errors=[]
for rel in staged:
 p=ROOT/rel
 if not p.exists(): continue
 if p.suffix=='.json':
  try: json.loads(p.read_text(encoding='utf8'))
  except Exception as e: errors.append(f'JSON parse {rel}: {e}')
 elif p.suffix=='.jsonl':
  for n,line in enumerate(p.read_text(encoding='utf8').splitlines(),1):
   if line.strip():
    try: json.loads(line)
    except Exception as e: errors.append(f'JSONL parse {rel}:{n}: {e}')
 if p.stat().st_size>90_000_000: errors.append(f'staged file over 90MB: {rel} ({p.stat().st_size})')
 if '/raw/' in f'/{rel}' or rel.endswith('/raw'): errors.append(f'raw path staged: {rel}')
 text=p.read_text(errors='ignore') if p.stat().st_size<5_000_000 and p.suffix in {'.py','.json','.jsonl','.md','.csv'} else ''
 for pat in [r'sk-[A-Za-z0-9]{20,}',r'ghp_[A-Za-z0-9]{20,}',r'github_pat_[A-Za-z0-9_]{20,}',r'AKIA[0-9A-Z]{16}']:
  if re.search(pat,text): errors.append(f'possible secret {rel}: {pat}')
subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=False)
print({'staged_files':len(staged),'json_checks':'performed','max_staged_bytes':max(( (ROOT/x).stat().st_size for x in staged if (ROOT/x).exists()),default=0),'errors':errors})
if errors: sys.exit(1)
