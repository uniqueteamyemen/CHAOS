from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
ROOT=Path('/home/ubuntu/CHAOS'); EXP=ROOT/'experiments/macro_plus_eia_energy'; NEXT=EXP/'next_phase'; IMP=NEXT/'importance'; OUT=NEXT/'report'; FIG=OUT/'figures'; FIG.mkdir(parents=True,exist_ok=True)
metrics=pd.read_csv(NEXT/'CAMPAIGN_METRICS_SUMMARY.csv'); base=pd.read_csv(EXP/'MODEL_BASELINE_COMPARISON_V1_1.csv')
full_test=base[(base.model=='TFT')&(base.split=='test')].iloc[0]; full_val=base[(base.model=='TFT')&(base.split=='validation')].iloc[0]
stab=metrics[metrics.family=='stability'].copy(); best=stab.sort_values(['val_MAE','val_RMSE']).iloc[0]
byenc=stab.groupby('encoder').agg(val_MAE_mean=('val_MAE','mean'),val_MAE_sd=('val_MAE','std'),test_MAE_mean=('test_MAE','mean'),test_MAE_sd=('test_MAE','std')).reset_index(); byseed=stab.groupby('seed').agg(val_MAE_mean=('val_MAE','mean'),val_MAE_sd=('val_MAE','std'),test_MAE_mean=('test_MAE','mean'),test_MAE_sd=('test_MAE','std')).reset_index(); stab.to_csv(OUT/'STABILITY_RESULTS_TABLE.csv',index=False); byenc.to_csv(OUT/'STABILITY_BY_ENCODER.csv',index=False); byseed.to_csv(OUT/'STABILITY_BY_SEED.csv',index=False)
abl=metrics[metrics.family=='ablation']; arms=[{'arm':'full_matrix_reference_v1_1','val_MAE':full_val.MAE,'val_RMSE':full_val.RMSE,'test_MAE':full_test.MAE,'test_RMSE':full_test.RMSE,'test_R2':full_test.R2,'test_directional_accuracy':full_test.directional_accuracy}]
for _,r in abl.iterrows(): arms.append({'arm':r.run_id.replace('ablation_','').replace('_seed17_enc5',''),'val_MAE':r.val_MAE,'val_RMSE':r.val_RMSE,'test_MAE':r.test_MAE,'test_RMSE':r.test_RMSE,'test_R2':r.test_R2,'test_directional_accuracy':r.test_directional_accuracy})
ablt=pd.DataFrame(arms); ablt.to_csv(OUT/'ABLATION_RESULTS_TABLE.csv',index=False)
th=metrics[metrics.family=='target_history_ablation']; tarms=[{'arm':'full_matrix_reference_v1_1','val_MAE':full_val.MAE,'val_RMSE':full_val.RMSE,'test_MAE':full_test.MAE,'test_RMSE':full_test.RMSE,'test_R2':full_test.R2,'test_directional_accuracy':full_test.directional_accuracy}]
for _,r in th.iterrows(): tarms.append({'arm':r.run_id.replace('target_history_','').replace('_seed17_enc5',''),'val_MAE':r.val_MAE,'val_RMSE':r.val_RMSE,'test_MAE':r.test_MAE,'test_RMSE':r.test_RMSE,'test_R2':r.test_R2,'test_directional_accuracy':r.test_directional_accuracy})
# Keep the explicit experimental arm name readable in the final table.
tht_name_map={'only':'target_history_only'}
tht=pd.DataFrame(tarms); tht['arm']=tht['arm'].replace(tht_name_map); tht.to_csv(OUT/'TARGET_HISTORY_RESULTS_TABLE.csv',index=False)
plt.style.use('seaborn-v0_8-whitegrid')
fig,ax=plt.subplots(figsize=(8,5))
for seed,g in stab.groupby('seed'): ax.plot(g.encoder,g.val_MAE,marker='o',label=f'seed {seed}')
ax.set(title='Stability Grid: validation MAE',xlabel='Encoder length (years)',ylabel='Validation MAE'); ax.legend(); fig.tight_layout(); fig.savefig(FIG/'01_stability_validation_mae.png',dpi=180); plt.close(fig)
fig,ax=plt.subplots(figsize=(10,5)); q=ablt.sort_values('test_MAE'); ax.bar(q.arm,q.test_MAE,color='#4472C4'); ax.set(title='Ablation: test MAE (descriptive)',ylabel='Test MAE'); ax.tick_params(axis='x',rotation=35); fig.tight_layout(); fig.savefig(FIG/'02_ablation_test_mae.png',dpi=180); plt.close(fig)
vi=pd.read_csv(IMP/'VARIABLE_SELECTION_STABILITY_SUMMARY.csv').sort_values('mean_importance',ascending=False); fig,ax=plt.subplots(figsize=(9,5)); q=vi.head(11).sort_values('mean_importance'); ax.barh(q.variable,q.mean_importance,color='#70AD47'); ax.set(title='Variable-selection mean importance across stability runs',xlabel='Mean importance'); fig.tight_layout(); fig.savefig(FIG/'03_variable_selection_importance.png',dpi=180); plt.close(fig)
ta=pd.read_csv(IMP/'TEMPORAL_ATTENTION_STABILITY_SUMMARY.csv'); order=['t-6','t-5','t-4','t-3','t-2','t-1','t']; ta['ord']=ta.encoder_position.map({x:i for i,x in enumerate(order)}); ta=ta.sort_values('ord'); fig,ax=plt.subplots(figsize=(8,5)); ax.errorbar(ta.encoder_position,ta.mean_attention,yerr=ta.std_across_runs,marker='o',capsize=4,color='#ED7D31'); ax.set(title='Temporal attention across stability runs',xlabel='Encoder position',ylabel='Mean attention +/- run SD'); fig.tight_layout(); fig.savefig(FIG/'04_temporal_attention.png',dpi=180); plt.close(fig)

def table(df,cols): return df[cols].to_markdown(index=False,floatfmt='.4f')
report=[]
report.append('# تقرير المرحلة التجريبية التالية — Stability / Ablation / Importance\n')
report.append('## الحالة التنفيذية\n\nاكتملت 9 تشغيلات Stability، و6 تشغيلات Ablation جديدة مع مرجع Full Matrix، وتشغيلتا Target-History Ablation، ثم تحليل variable-selection وattention وencoder-step importance. لم تُشغّل Reverse Extraction أو surrogate validation، ولم تُجمع بيانات جديدة أو تُعدّل raw data. تم اختيار إعداد stability من validation فقط؛ test وصفي.\n')
report.append(f'## 1. Stability Grid\n\nأفضل تشغيل وفق validation MAE هو **{best.run_id}**: seed={int(best.seed)}، encoder={int(best.encoder)}، validation MAE={best.val_MAE:.4f}، validation RMSE={best.val_RMSE:.4f}.\n\n{table(byenc,["encoder","val_MAE_mean","val_MAE_sd","test_MAE_mean","test_MAE_sd"])}\n\nالفروق عبر encoder متقاربة، وأثر seed واضح؛ لذلك لا توجد configuration مستقرة بقوة حتى الآن.\n\n![Stability validation MAE](figures/01_stability_validation_mae.png)\n')
report.append(f'## 2. Ablation Experiments\n\n{table(ablt.sort_values("val_MAE"),["arm","val_MAE","val_RMSE","test_MAE","test_RMSE","test_R2","test_directional_accuracy"])}\n\nفي validation كان WDI-only الأفضل بين arms الجديدة MAE={ablt[ablt.arm=="wdi_only"].val_MAE.iloc[0]:.4f}. في test كان EIA-only أقل MAE={ablt[ablt.arm=="eia_only"].test_MAE.iloc[0]:.4f}، لكن test لم يُستخدم للاختيار. التناقض بين validation وtest يمنع نسبة أثر ثابت لأي domain.\n\n![Ablation test MAE](figures/02_ablation_test_mae.png)\n')
report.append(f'## 3. Target-History Ablation\n\n{table(tht.sort_values("val_MAE"),["arm","val_MAE","val_RMSE","test_MAE","test_RMSE","test_R2","test_directional_accuracy"])}\n\ntarget-history-only أضعف على test من exogenous-only وFull Matrix. الفارق الصغير بين exogenous-only وFull Matrix لا يكفي لإثبات مساهمة مستقلة مستقرة لتاريخ الهدف.\n')
report.append(f'## 4. Variable / Temporal Analysis\n\n{table(vi.head(11),["variable","runs","mean_importance","std_across_runs","top3_run_count"])}\n\nظهر تاريخ الهدف ومتغيرا EIA ضمن أعلى ثلاثة في 9/9 تشغيلات وفق هذا المقياس الوصفي. هذا candidate descriptive pattern فقط؛ لا يثبت السببية.\n\n![Variable importance](figures/03_variable_selection_importance.png)\n\n### المواقع الزمنية\n\n{table(ta,["encoder_position","runs","mean_attention","std_across_runs","top_run_count"])}\n\nلم يبلغ أي موقع زمني واحد 6/9 كـtop attention؛ لذلك لا يوجد lag مستقر مسجل.\n\n![Temporal attention](figures/04_temporal_attention.png)\n')
report.append('''## 5. Candidate patterns والنتائج السلبية

| المرشح | الحالة | الدليل الحالي | القيد |
|---|---|---|---|
| target history ضمن أعلى 3 variables | Candidate descriptive | 9/9 stability runs | ليس causal ويحتاج robustness |
| EIA energy per capita ضمن أعلى 3 | Candidate descriptive | 9/9 stability runs | لا يثبت أن الطاقة سبب |
| EIA energy per GDP ضمن أعلى 3 | Candidate descriptive | 9/9 stability runs | لا يثبت السببية أو التعميم |
| lag/temporal position | لا candidate مستقر | لا موقع بلغ 6/9 | الانتباه ليس اختبار lag سببي |
''')
report.append('''## 6. التناقضات والقيود

1. العقد v1.1 raw-value mode، ولم يُستخدم تطبيع أو imputation.
2. أفضل validation arm ليس أفضل test arm؛ لا يجوز اختيار EIA-only من test.
3. Stability استخدمت support start=2008 لمقارنة encoder 3/5/7، بينما baseline الأصلي يبدأ من 2006؛ لذلك ليست أرقامها متطابقة تماماً مع baseline الأول.
4. Target-history arms B وD متطابقان دلالياً؛ شُغّل exogenous-only مرة واحدة وسُجل التكرار.
5. Full Matrix هو مرجع baseline v1.1 أُنجز بـ max_epochs=50، بينما أذرع المرحلة الجديدة أُنجزت بـ max_epochs=25؛ لذلك المقارنة المرجعية ليست تطابقاً كاملاً في ميزانية التدريب.
6. لم تُنفذ quantile uncertainty أو event holdout أو Reverse Extraction أو surrogate gate.
''')
report.append('## 7. القرار المرحلي\n\nتُسجل النتائج كـexploratory candidate evidence. لا توجد configuration أو variable أو lag مؤهلة للترقية إلى validated structural pattern. لا يبدأ Reverse Extraction تلقائياً؛ يحتاج عقداً مستقلاً ومراجعة لاحقة.\n')
report.append('''## 8. السجل والتحقق

السجل المضغوط لجميع التشغيلات والمرجع محفوظ في `NEXT_PHASE_EXPERIMENT_REGISTRY.jsonl`، بينما التفاصيل الكاملة للحملة في `CAMPAIGN_RUN_RESULTS.json`. أُنجز QA manifest في `NEXT_PHASE_QA_MANIFEST.json`، ويتضمن counts وhashes للرسوم والـcheckpoints والتحقق من ثبات ملفات raw مقارنةً بـHEAD. سجلات فشل وإصلاح مولد التقرير محفوظة في `logs/`، ولا تُحذف failures من provenance.

الملفات الداعمة الأساسية هي `STABILITY_RESULTS_TABLE.csv`، `STABILITY_BY_ENCODER.csv`، `STABILITY_BY_SEED.csv`، `ABLATION_RESULTS_TABLE.csv`، `TARGET_HISTORY_RESULTS_TABLE.csv`، وملفات `importance/`، إضافة إلى الرسوم الأربعة في `figures/`.

## 9. نقطة التوقف

هذه المرحلة مكتملة من ناحية التشغيل والتوثيق، لكنها لا تمنح اعتماداً بنيوياً أو سببياً لأي متغير أو lag. لم يبدأ Reverse Extraction، ولن يبدأ تلقائياً؛ التوقف هنا بانتظار مراجعة المستخدم وعقد مستقل للمرحلة التالية.
''')
(OUT/'NEXT_EXPERIMENTAL_PHASE_REPORT_AR.md').write_text('\n'.join(report),encoding='utf-8')
summary={'stability_runs':9,'ablation_runs_new':6,'full_reference_not_retrained':True,'target_history_runs':2,'importance_runs':9,'best_validation_run':best.run_id,'candidate_pattern_count':3,'stable_lag_candidate_count':0,'reverse_extraction_run':False,'surrogate_run':False,'raw_data_modified':False,'test_used_for_selection':False}
(OUT/'NEXT_PHASE_REPORT_SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(summary,ensure_ascii=False,indent=2))
