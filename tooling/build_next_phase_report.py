from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
ROOT=Path('/home/ubuntu/CHAOS'); EXP=ROOT/'experiments/macro_plus_eia_energy'; NEXT=EXP/'next_phase'; IMP=NEXT/'importance'; OUT=NEXT/'report'; OUT.mkdir(parents=True,exist_ok=True); FIG=OUT/'figures'; FIG.mkdir(exist_ok=True)
metrics=pd.read_csv(NEXT/'CAMPAIGN_METRICS_SUMMARY.csv')
base=pd.read_csv(EXP/'MODEL_BASELINE_COMPARISON_V1_1.csv'); base=base[base.entity_code.isna()]
full_tft=base[(base.model=='TFT') & (base.split=='test')].iloc[0].to_dict()
full_val=base[(base.model=='TFT') & (base.split=='validation')].iloc[0].to_dict()
# stability summaries: selection strictly by validation MAE
stab=metrics[metrics.family=='stability'].copy(); stab_by_enc=stab.groupby('encoder').agg(val_MAE_mean=('val_MAE','mean'),val_MAE_std=('val_MAE','std'),test_MAE_mean=('test_MAE','mean'),test_MAE_std=('test_MAE','std'),val_RMSE_mean=('val_RMSE','mean'),test_RMSE_mean=('test_RMSE','mean')).reset_index()
stab_by_seed=stab.groupby('seed').agg(val_MAE_mean=('val_MAE','mean'),val_MAE_std=('val_MAE','std'),test_MAE_mean=('test_MAE','mean'),test_MAE_std=('test_MAE','std')).reset_index()
best=stab.sort_values(['val_MAE','val_RMSE']).iloc[0]
# ablation: all arms + full reference from contract baseline (not duplicated)
abl=metrics[metrics.family=='ablation'].copy(); ablt=pd.DataFrame([{'run_id':'full_matrix_reference_v1_1','arm':'full_matrix','val_MAE':full_val['MAE'],'val_RMSE':full_val['RMSE'],'test_MAE':full_tft['MAE'],'test_RMSE':full_tft['RMSE'],'test_R2':full_tft['R2'],'test_directional_accuracy':full_tft['directional_accuracy']}])
for _,r in abl.iterrows(): ablt=pd.concat([ablt,pd.DataFrame([{'run_id':r.run_id,'arm':r.run_id.replace('ablation_','').replace('_seed17_enc5',''),'val_MAE':r.val_MAE,'val_RMSE':r.val_RMSE,'test_MAE':r.test_MAE,'test_RMSE':r.test_RMSE,'test_R2':r.test_R2,'test_directional_accuracy':r.test_directional_accuracy}])],ignore_index=True)
# target-history arms + full ref
th=metrics[metrics.family=='target_history_ablation'].copy(); tht=pd.DataFrame([{'run_id':'full_matrix_reference_v1_1','arm':'full_matrix','val_MAE':full_val['MAE'],'val_RMSE':full_val['RMSE'],'test_MAE':full_tft['MAE'],'test_RMSE':full_tft['RMSE'],'test_R2':full_tft['R2'],'test_directional_accuracy':full_tft['directional_accuracy']}])
for _,r in th.iterrows(): tht=pd.concat([tht,pd.DataFrame([{'run_id':r.run_id,'arm':r.run_id.replace('target_history_','').replace('_seed17_enc5',''),'val_MAE':r.val_MAE,'val_RMSE':r.val_RMSE,'test_MAE':r.test_MAE,'test_RMSE':r.test_RMSE,'test_R2':r.test_R2,'test_directional_accuracy':r.test_directional_accuracy}])],ignore_index=True)
stab.to_csv(OUT/'STABILITY_RESULTS_TABLE.csv',index=False); stab_by_enc.to_csv(OUT/'STABILITY_BY_ENCODER.csv',index=False); stab_by_seed.to_csv(OUT/'STABILITY_BY_SEED.csv',index=False); ablt.to_csv(OUT/'ABLATION_RESULTS_TABLE.csv',index=False); tht.to_csv(OUT/'TARGET_HISTORY_RESULTS_TABLE.csv',index=False)
# plots
plt.style.use('seaborn-v0_8-whitegrid')
fig,ax=plt.subplots(figsize=(8,5));
for seed,g in stab.groupby('seed'): ax.plot(g.encoder,g.val_MAE,marker='o',label=f'seed {seed}')
ax.set_title('Stability Grid: validation MAE (selection metric)'); ax.set_xlabel('Encoder length (years)'); ax.set_ylabel('Validation MAE'); ax.legend(); fig.tight_layout(); fig.savefig(FIG/'01_stability_validation_mae.png',dpi=180); plt.close(fig)
fig,ax=plt.subplots(figsize=(10,5)); q=ablt.sort_values('test_MAE'); ax.bar(q.arm,q.test_MAE,color=['#4472C4' if x!='full_matrix' else '#C00000' for x in q.arm]); ax.set_title('Ablation: test MAE (descriptive, not used for selection)'); ax.set_ylabel('Test MAE'); ax.tick_params(axis='x',rotation=35); fig.tight_layout(); fig.savefig(FIG/'02_ablation_test_mae.png',dpi=180); plt.close(fig)
vi=pd.read_csv(IMP/'VARIABLE_SELECTION_STABILITY_SUMMARY.csv').sort_values('mean_importance',ascending=False).head(11); fig,ax=plt.subplots(figsize=(9,5)); ax.barh(vi.variable.iloc[::-1],vi.mean_importance.iloc[::-1],color='#70AD47'); ax.set_title('Variable-selection mean importance across stability runs'); ax.set_xlabel('Mean importance'); fig.tight_layout(); fig.savefig(FIG/'03_variable_selection_importance.png',dpi=180); plt.close(fig)
ta=pd.read_csv(IMP/'TEMPORAL_ATTENTION_STABILITY_SUMMARY.csv'); order=['t-6','t-5','t-4','t-3','t-2','t-1','t']; ta['ord']=ta.encoder_position.map({x:i for i,x in enumerate(order)}); ta=ta.sort_values('ord'); fig,ax=plt.subplots(figsize=(8,5)); ax.errorbar(ta.encoder_position,ta.mean_attention,yerr=ta.std_across_runs,marker='o',capsize=4,color='#ED7D31'); ax.set_title('Temporal attention across stability runs'); ax.set_xlabel('Encoder position'); ax.set_ylabel('Mean attention ± run SD'); fig.tight_layout(); fig.savefig(FIG/'04_temporal_attention.png',dpi=180); plt.close(fig)
# Markdown report
def md_table(df,cols):
 return df[cols].to_markdown(index=False,floatfmt='.4f')
report=[]
report.append('# تقرير المرحلة التجريبية التالية — Stability / Ablation / Importance\n')
report.append('## الحالة التنفيذية\n\nاكتملت 9 تشغيلات Stability (3 seeds × 3 encoder lengths)، و6 تشغيلات Ablation الجديدة مع مرجع Full Matrix، وتشغيلتا Target-History Ablation، ثم تحليل variable-selection وattention وencoder-step importance على checkpoints الاستقرار. لم تُشغّل Reverse Extraction أو surrogate validation، ولم تُجمع بيانات جديدة أو تُعدّل raw data. كل نتائج test أدناه وصفية؛ الاختيار تم من validation فقط.\n')
report.append('## 1. Stability Grid\n\nالاختيار المسموح هو أقل validation MAE فقط. أفضل تشغيل وفق هذا القيد هو **%s**: seed=%d، encoder=%d، validation MAE=%.4f، validation RMSE=%.4f.\n\n%s\n' % (best.run_id,best.seed,best.encoder,best.val_MAE,best.val_RMSE,md_table(stab_by_enc,['encoder','val_MAE_mean','val_MAE_std','test_MAE_mean','test_MAE_std'])))
report.append('تُظهر النتائج أن الفروق عبر encoder صغيرة ومتداخلة، بينما يظهر أثر seed واضح نسبياً. لذلك لا يوجد بعد دليل على configuration مستقرة بقوة؛ يمكن استخدام تشغيل validation الأفضل كمرجع وصفي فقط، لا كحقيقة نهائية.\n\n![Stability validation MAE](figures/01_stability_validation_mae.png)\n')
report.append('## 2. Ablation Experiments\n\nالمرجع Full Matrix هو TFT baseline v1.1 السابق، ولم يُعاد تدريبه.\n\n%s\n' % md_table(ablt.sort_values('val_MAE'),['arm','val_MAE','val_RMSE','test_MAE','test_RMSE','test_R2','test_directional_accuracy']))
report.append('في validation، كان WDI-only الأفضل بين arms الجديدة (MAE %.4f)، بينما كان WDI+EIA قريباً منه (%.4f)، والمرجع Full Matrix أعلى (%.4f). في test، حقق EIA-only أقل MAE (%.4f)، لكن هذا لا يُستخدم لاختيار مجال أو configuration، لأنه test مقفل ووصفه لاحق للتجربة. التناقض بين validation وtest يعني أن إضافة المجالات لا تعطي ترتيباً مستقراً من هذه الحملة المحدودة.\n\n![Ablation test MAE](figures/02_ablation_test_mae.png)\n' % (float(ablt[ablt.arm=='wdi_only'].val_MAE.iloc[0]),float(ablt[ablt.arm=='wdi_eia'].val_MAE.iloc[0]),float(ablt[ablt.arm=='full_matrix'].val_MAE.iloc[0]),float(ablt[ablt.arm=='eia_only'].test_MAE.iloc[0])))
report.append('## 3. Target-History Ablation\n\n%s\n' % md_table(tht.sort_values('val_MAE'),['arm','val_MAE','val_RMSE','test_MAE','test_RMSE','test_R2','test_directional_accuracy']))
report.append('على test، كان exogenous-only قريباً جداً من Full Matrix، بينما target-history-only أضعف. الفارق الصغير بين exogenous-only وFull Matrix لا يكفي لاعتبار تاريخ الهدف ذا مساهمة مستقلة مؤكدة؛ يلزم تكرار عبر seeds وتثبيت pre-registered comparison قبل أي استنتاج أقوى.\n')
report.append('## 4. Variable / Temporal Analysis\n\nأُجري التحليل على مخرجات forward الأصلية عبر checkpoints التسعة. أعلى المتغيرات وفق متوسط variable-selection كانت:\n\n%s\n' % md_table(vi,['variable','runs','mean_importance','std_across_runs','top3_run_count']))
report.append('ظهر تاريخ الهدف `wdi__NY_GDP_MKTP_KD_ZG` ومتغيرا EIA (`energy_consumption_per_capita` و`energy_consumption_per_gdp`) ضمن أعلى ثلاثة في التشغيلات التسع وفق قاعدة هذا التقرير. هذا **candidate descriptive pattern** فقط، وليس causal pattern؛ الأهمية المستخرجة من TFT قد تعكس تمثيلاً أو اعتماداً تنبؤياً ولا تثبت التأثير.\n\n![Variable importance](figures/03_variable_selection_importance.png)\n')
report.append('### المواقع الزمنية\n\n%s\n' % md_table(ta,['encoder_position','runs','mean_attention','std_across_runs','top_run_count']))
report.append('لا يوجد موقع زمني واحد فاز في 6/9 تشغيلات وفق معيار top attention؛ لذلك لم يُسجّل lag مستقراً كـcandidate temporal pattern. التوزيع بين `t` و`t-2` متقارب، ولا يجوز تحويله إلى causal lag.\n\n![Temporal attention](figures/04_temporal_attention.png)\n')
report.append('## 5. Candidate patterns ونتائج سلبية\n\n| المرشح | الحالة | الدليل الحالي | القيد |
|---|---|---|---|
| target history ضمن أعلى 3 variables | Candidate descriptive | 9/9 stability runs | ليس causal؛ يحتاج robustness وablation مستقل |
| EIA energy per capita ضمن أعلى 3 | Candidate descriptive | 9/9 stability runs | لا يثبت أن الطاقة سبب؛ قد يكون تمثيلاً أو redundancy |
| EIA energy per GDP ضمن أعلى 3 | Candidate descriptive | 9/9 stability runs | لا يثبت السببية أو قابلية التعميم |
| lag/temporal position | لا candidate مستقر | لا موقع بلغ 6/9 كـtop attention | الانتباه ليس اختبار lag سببي |
')
report.append('## 6. تناقضات وقيود يجب حفظها\n\n1. العقد v1.1 raw-value mode، لكن TFT نفسه بقي حساساً لاختلاف مقاييس المتغيرات؛ لم نحل ذلك بتطبيع لأن التحويل غير معتمد.\n2. أفضل validation arm ليس أفضل test arm؛ هذا متوقع كإشارة إلى عدم استقرار الاختيار، وليس مبرراً لاختيار EIA-only من test.\n3. Stability grid استخدمت support start=2008 للحفاظ على مقارنة encoder 3/5/7، بينما baseline العقد الأصلي يبدأ target من 2006؛ نتائج stability ليست مطابقة تماماً لنفس حجم train في baseline.\n4. Target-history arms B وD في الخطة متطابقان دلالياً؛ شُغّل exogenous-only مرة واحدة وسُجل التكرار.\n5. لم تُنفذ quantile uncertainty، event holdout، Reverse Extraction، أو surrogate gate.\n')
report.append('## 7. القرار المرحلي\n\nتُسجل النتائج كـ**exploratory candidate evidence**. لا توجد حالياً configuration أو variable أو lag مؤهلة للترقية إلى validated structural pattern. الخطوة التالية المنفصلة، بعد مراجعة المستخدم، يمكن أن تكون تصميم Reverse Extraction بعقد أحداث مستقل، لكن لا يبدأ تلقائياً من هذا التقرير.\n\n## الملفات الداعمة\n\n- `STABILITY_RESULTS_TABLE.csv` و`STABILITY_BY_ENCODER.csv` و`STABILITY_BY_SEED.csv`\n- `ABLATION_RESULTS_TABLE.csv`\n- `TARGET_HISTORY_RESULTS_TABLE.csv`\n- `importance/VARIABLE_SELECTION_STABILITY_SUMMARY.csv`\n- `importance/TEMPORAL_ATTENTION_STABILITY_SUMMARY.csv`\n- `importance/CANDIDATE_TEMPORAL_STRUCTURAL_PATTERNS.csv`\n- `CAMPAIGN_RUN_RESULTS.json`\n')
(OUT/'NEXT_EXPERIMENTAL_PHASE_REPORT_AR.md').write_text('\n'.join(report),encoding='utf-8')
summary={'stability_runs':9,'ablation_runs_new':6,'full_reference_not_retrained':True,'target_history_runs':2,'importance_runs':9,'best_validation_run':best.run_id,'candidate_pattern_count':3,'stable_lag_candidate_count':0,'reverse_extraction_run':False,'surrogate_run':False,'raw_data_modified':False,'test_used_for_selection':False}
(OUT/'NEXT_PHASE_REPORT_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
