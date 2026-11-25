from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
GATE = ROOT / 'readiness_gate'
PLOT = ROOT / 'readiness_gate' / 'visuals'
PLOT.mkdir(exist_ok=True)

with (GATE / 'VARIABLE_LEVEL_COVERAGE_MATRIX_GAP_AUGMENTED.csv').open(encoding='utf-8', newline='') as f:
    coverage = list(csv.DictReader(f))
with (GATE / 'CANDIDATE_MATRIX_COMPARISON_GAP_AUGMENTED.json').open(encoding='utf-8') as f:
    comparison = json.load(f)['comparison']
with (GATE / 'ANNUAL_PANEL_READINESS_SUMMARY.json').open(encoding='utf-8') as f:
    base = json.load(f)

plt.rcParams.update({'font.family':'DejaVu Sans','axes.titleweight':'bold','figure.dpi':150})

# Plot 1: selected WDI/IMF variable-level coverage.
annual = [r for r in coverage if r['dataset_id'] in ('worldbank_wdi_bulk_csv','imf_weo_apr2026_current')]
annual = sorted(annual, key=lambda r: float(r['panel_coverage_ratio'] or 0))
labels=[]; vals=[]; colors=[]
for r in annual:
    labels.append(f"{('WDI' if r['dataset_id']=='worldbank_wdi_bulk_csv' else 'IMF')} {r['variable_id']}")
    vals.append(float(r['panel_coverage_ratio'])*100)
    colors.append('#2A6FBB' if r['dataset_id']=='worldbank_wdi_bulk_csv' else '#D97706')
fig, ax = plt.subplots(figsize=(11,8))
y=np.arange(len(labels))
ax.barh(y, vals, color=colors)
ax.set_yticks(y, labels, fontsize=8)
ax.set_xlim(80,101)
ax.set_xlabel('Observed cells in 2000–2024 (% of active-entity envelope)')
ax.set_title('Variable-level annual coverage: selected WDI and IMF WEO variables')
ax.grid(axis='x', alpha=.25)
for yy,v in zip(y,vals): ax.text(v+.15,yy,f'{v:.2f}%',va='center',fontsize=8)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color='#2A6FBB',label='World Bank WDI'),Patch(color='#D97706',label='IMF WEO current')],loc='lower right')
fig.tight_layout()
fig.savefig(PLOT/'01_annual_variable_coverage_wdi_imf.png',bbox_inches='tight')
plt.close(fig)

# Plot 2: candidate matrices, coverage and complete entities.
names=list(comparison)
pretty={
 'macro_with_levels_previous':'Previous macro',
 'macro_plus_eia_energy':'Macro + EIA energy',
 'macro_plus_ucdp_conflict':'Macro + UCDP',
 'macro_plus_eia_plus_ucdp':'Macro + EIA + UCDP',
}
coverage_vals=[comparison[n]['cell_coverage_ratio']*100 for n in names]
complete=[comparison[n]['entities_complete_all_selected_variables_for_all_25_years'] for n in names]
fig,(ax1,ax2)=plt.subplots(1,2,figsize=(12,5.2))
x=np.arange(len(names)); bar_colors=['#4C78A8','#59A14F','#F28E2B','#B279A2']
ax1.bar(x,coverage_vals,color=bar_colors)
ax1.set_xticks(x,[pretty[n] for n in names],rotation=25,ha='right',fontsize=8)
ax1.set_ylim(85,100); ax1.set_ylabel('Observed value cells (%)'); ax1.set_title('Coverage')
ax1.grid(axis='y',alpha=.25)
for i,v in enumerate(coverage_vals): ax1.text(i,v+.25,f'{v:.2f}%',ha='center',fontsize=8)
ax2.bar(x,complete,color=bar_colors)
ax2.set_xticks(x,[pretty[n] for n in names],rotation=25,ha='right',fontsize=8)
ax2.set_ylim(0,155); ax2.set_ylabel('Countries complete for every selected variable')
ax2.set_title('25-year complete countries'); ax2.grid(axis='y',alpha=.25)
for i,v in enumerate(complete): ax2.text(i,v+2,str(v),ha='center',fontsize=9)
fig.suptitle('Gap-augmented candidate matrices — raw readiness comparison',fontweight='bold')
fig.tight_layout(rect=[0,0,1,.94])
fig.savefig(PLOT/'02_candidate_matrix_comparison.png',bbox_inches='tight')
plt.close(fig)

# Plot 3: coverage funnel / cross-domain scope.
labels=['WDI×IMF common\ncountry IDs','EIA selected\nper concept','UCDP exact-normalized\nname matches','NOAA GSOM\nselected stations']
values=[base['identifier_intersection_any_selected_variable'],189,comparison and 155,9]
fig,ax=plt.subplots(figsize=(9,5.5))
ax.bar(labels,values,color=['#4C78A8','#59A14F','#F28E2B','#76B7B2'])
ax.set_ylim(0,210); ax.set_ylabel('Count of country IDs / stations')
ax.set_title('Scope of the three added data layers')
ax.grid(axis='y',alpha=.25)
for i,v in enumerate(values): ax.text(i,v+4,str(v),ha='center',fontweight='bold')
fig.text(.5,.01,'Counts are not interchangeable: GSOM is station-month scope; UCDP is a conservative name crosswalk; EIA is per concept.',ha='center',fontsize=8)
fig.tight_layout(rect=[0,.05,1,1])
fig.savefig(PLOT/'03_scope_and_gap_funnel.png',bbox_inches='tight')
plt.close(fig)

# Plot 4: NOAA native monthly PRCP station completeness.
gsom=[r for r in coverage if r['dataset_id']=='noaa_gsom_monthly_selected_stations']
gsom=sorted(gsom,key=lambda r: float(r['panel_coverage_ratio'] or 0))
labels=[r['variable_id'] for r in gsom]; vals=[float(r['panel_coverage_ratio'])*100 for r in gsom]
fig,ax=plt.subplots(figsize=(10,5.2))
y=np.arange(len(labels)); ax.barh(y,vals,color='#76B7B2')
ax.set_yticks(y,labels,fontsize=8); ax.set_xlim(0,105); ax.set_xlabel('Observed native monthly PRCP cells in 2000–2024 (%)')
ax.set_title('NOAA GSOM PRCP coverage by selected station — no daily-to-monthly conversion')
ax.grid(axis='x',alpha=.25)
for yy,v in zip(y,vals): ax.text(v+1,yy,f'{v:.2f}%',va='center',fontsize=8)
fig.tight_layout(); fig.savefig(PLOT/'04_gsom_prcp_station_coverage.png',bbox_inches='tight'); plt.close(fig)

# Numeric manifest for report.
manifest={'plots':[
 {'file':'01_annual_variable_coverage_wdi_imf.png','source':'VARIABLE_LEVEL_COVERAGE_MATRIX_GAP_AUGMENTED.csv','claim':'selected WDI/IMF annual variable coverage'},
 {'file':'02_candidate_matrix_comparison.png','source':'CANDIDATE_MATRIX_COMPARISON_GAP_AUGMENTED.json','claim':'four candidate matrices coverage and complete countries'},
 {'file':'03_scope_and_gap_funnel.png','source':'ANNUAL_PANEL_READINESS_SUMMARY.json + gap augmentation outputs','claim':'scope counts for EIA/UCDP/GSOM'},
 {'file':'04_gsom_prcp_station_coverage.png','source':'VARIABLE_LEVEL_COVERAGE_MATRIX_GAP_AUGMENTED.csv','claim':'native monthly PRCP coverage by station'},
], 'no_synthetic_data':True,'no_experiment_or_model':True}
(GATE/'visuals/visual_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False,indent=2))
