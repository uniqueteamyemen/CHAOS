from pathlib import Path
import pandas as pd

p = Path('/home/ubuntu/market_intelligence_workspace/catalog_first/staged/imf/weo/WEOApr2026all.xlsx')
df = pd.read_excel(p, sheet_name='Countries', usecols=['INDICATOR.ID','INDICATOR','UNIT','FREQUENCY'])
ids = sorted(df['INDICATOR.ID'].dropna().astype(str).unique())
for code in ['NGDP_RPCH','PCPI','BCA_NGDPD','BCA_GDP_BP6','GGXWDG_NGDP','GGX_NGDP','TM_RPCH','TX_RPCH','LUR','PPPEX','NGDP','NGDPD','NID_NGDP']:
    matches = [x for x in ids if x == code or x.startswith(code + '.')]
    print(code, matches)
print('\nselected rows:')
for code in ['NGDP_RPCH','PCPI','BCA_NGDPD','GGXWDG_NGDP','TM_RPCH','TX_RPCH','LUR','PPPEX']:
    sub=df[df['INDICATOR.ID'].astype(str).eq(code)].drop_duplicates()
    if not sub.empty:
        print(sub.to_string(index=False))
