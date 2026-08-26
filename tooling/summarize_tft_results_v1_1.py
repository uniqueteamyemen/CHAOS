import json
from pathlib import Path
import pandas as pd
ROOT=Path('/home/ubuntu/CHAOS'); EXP=ROOT/'experiments/macro_plus_eia_energy'
comp=pd.read_csv(EXP/'MODEL_BASELINE_COMPARISON_V1_1.csv')
test=comp[comp.split=='test'].copy(); tft=test[test.model=='TFT'].iloc[0]; best=test[test.model!='TFT'].sort_values('MAE').iloc[0]
per=pd.read_csv(EXP/'TFT_TEST_PER_ENTITY_METRICS.csv')
result={'tft_test':tft.to_dict(),'best_baseline_test':best.to_dict(),'improvement_vs_best_baseline':{'MAE_abs':float(best.MAE-tft.MAE),'MAE_pct':float((best.MAE-tft.MAE)/best.MAE*100),'RMSE_abs':float(best.RMSE-tft.RMSE),'RMSE_pct':float((best.RMSE-tft.RMSE)/best.RMSE*100),'R2_delta':float(tft.R2-best.R2),'directional_accuracy_delta':float(tft.directional_accuracy-best.directional_accuracy)},'tft_per_entity_test_mae':{'median':float(per.MAE.median()),'q25':float(per.MAE.quantile(.25)),'q75':float(per.MAE.quantile(.75)),'min':float(per.MAE.min()),'max':float(per.MAE.max()),'entities_below_1':int((per.MAE<1).sum()),'entities_above_5':int((per.MAE>5).sum())},'test_model_order_by_mae':test.sort_values('MAE')[['model','MAE','RMSE','R2','directional_accuracy']].to_dict(orient='records')}
(EXP/'TFT_RESULT_SUMMARY_V1_1.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(result,ensure_ascii=False,indent=2))
