from pathlib import Path
import pandas as pd

ROOT=Path('/home/ubuntu/market_intelligence_workspace/catalog_first')
wdi_country=pd.read_csv(ROOT/'staged/worldbank/wdi_csv/WDICountry.csv', dtype=str)
wdi_country['Region']=wdi_country['Region'].fillna('').str.strip()
wdi_codes=set(wdi_country.loc[wdi_country['Region'].ne(''),'Country Code'].dropna())
all_wdi=set(wdi_country['Country Code'].dropna())
weo=pd.read_excel(ROOT/'staged/imf/weo/WEOApr2026all.xlsx', sheet_name='Countries', usecols=['COUNTRY.ID','COUNTRY'])
weo_codes=set(weo['COUNTRY.ID'].dropna().astype(str))
common=all_wdi & weo_codes
common_country=common & wdi_codes
print('WDI all ids:',len(all_wdi))
print('WDI with nonempty Region:',len(wdi_codes))
print('WEO Countries IDs:',len(weo_codes))
print('common all:',len(common))
print('common country-level by WDI Region:',len(common_country))
print('excluded from common due blank WDI Region:',sorted(common-common_country))
print('\nexcluded names:')
print(wdi_country[wdi_country['Country Code'].isin(common-common_country)][['Country Code','Short Name','Region']].to_string(index=False))
print('\ncommon country codes sample:',sorted(common_country)[:30])
