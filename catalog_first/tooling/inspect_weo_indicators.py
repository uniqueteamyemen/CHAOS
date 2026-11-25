from __future__ import annotations

from pathlib import Path
import pandas as pd

p = Path('/home/ubuntu/market_intelligence_workspace/catalog_first/staged/imf/weo/WEOApr2026all.xlsx')
df = pd.read_excel(p, sheet_name='Countries')
cols = ['INDICATOR.ID', 'INDICATOR', 'INDICATOR.Description', 'FREQUENCY', 'SCALE', 'UNIT']
out = df[cols].drop_duplicates().sort_values('INDICATOR.ID')
for _, r in out.iterrows():
    if any(k in str(r['INDICATOR.ID']).upper() + ' ' + str(r['INDICATOR']).upper() for k in ['NGDP_RPCH', 'PCPI_PCH', 'BCA_NGDPD', 'BCA_GDP_BP6', 'GGXWDG_NGDP', 'GGX_NGDP', 'TM_RPCH', 'TX_RPCH', 'LUR', 'PPPEX']):
        print(' | '.join(str(r.get(c, '')) for c in cols))
print('unique indicator rows:', len(out))
