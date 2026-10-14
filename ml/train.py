"""Reproducible offline workflow. Never exposes raw PII in outputs."""
import argparse, hashlib, json, platform, re, warnings, shutil
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import sklearn
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.frozen import FrozenEstimator
from sklearn.model_selection import TimeSeriesSplit, cross_validate
from sklearn.metrics import (roc_auc_score, average_precision_score, brier_score_loss,
    precision_score, recall_score, f1_score, confusion_matrix, roc_curve, precision_recall_curve)
from sklearn.inspection import permutation_importance
from ml.features import NUMERIC, CATEGORICAL, DERIVED, FEATURES, EXCLUDED, engineer

ROOT = Path(__file__).resolve().parents[1]
def dump(path, value):
    path.write_text(json.dumps(value, indent=2, default=str))

def ingest(path):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        a = pd.read_excel(path, sheet_name='Application Data')
        b = pd.read_excel(path, sheet_name='Loan Performance')
    required = set(FEATURES + ['customer_id','application_when'])
    if not required.issubset(a) or not {'idLoan','flgGood'}.issubset(b):
        raise ValueError('Workbook schema does not match the documented input contract')
    if not b.flgGood.isin(['Good','Bad']).all():
        raise ValueError('Unexpected loan labels')
    # Excel numeric IDs need string conversion; pad only plausible shortened IDs.
    a['key'] = a.customer_id.astype(str).str.strip().str.lower().str.zfill(10)
    b['key'] = b.idLoan.astype(str).str.split('-').str[0].str.strip().str.lower().str.zfill(10)
    valid = a.key.str.fullmatch('[0-9a-f]{10}')
    if a.loc[valid,'key'].duplicated().any() or b.idLoan.duplicated().any():
        raise ValueError('Duplicate primary identifiers require manual adjudication')
    first = b[b.idLoan.str.endswith('-01')].copy()
    if first.key.duplicated().any():
        raise ValueError('First-loan relationship is not one to one')
    d = a[valid].merge(first[['key','flgGood']], on='key', how='inner', validate='one_to_one')
    d = d.sort_values('application_when', kind='stable').reset_index(drop=True)
    if len(d)<100 or d.flgGood.nunique()!=2:
        raise ValueError('Insufficient labeled data')
    quality = {
        'application_rows':len(a),'performance_rows':len(b),'performance_customers':b.key.nunique(),
        'repeat_loan_rows':len(b)-len(first),'malformed_application_ids':int((~valid).sum()),
        'unmatched_valid_applications':int(valid.sum()-len(d)), 'matched_first_loans':len(d),
        'unmatched_first_loan_outcomes':len(first)-len(d),
        'conflicting_repeat_customer_labels':int((b.groupby('key').flgGood.nunique()>1).sum()),
        'numeric_application_ids':int(a.customer_id.map(lambda v:not isinstance(v,str)).sum()),
        'bad':int((d.flgGood=='Bad').sum()),'good':int((d.flgGood=='Good').sum()),
        'date_min':str(d.application_when.min()),'date_max':str(d.application_when.max()),
        'missing_by_column':a.drop(columns='key').isna().sum().to_dict(),
        'relationship_assumption':'customer_id matches idLoan prefix; -01 is first loan. Owner confirmation required.',
        'label_assumption':'Bad=1; no definition or observation horizon supplied.',
        'source_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        'excluded_features':EXCLUDED,
        'score_extreme_counts':{c:int((a[c]<300).sum()) for c in NUMERIC if c.startswith('raw_')},
    }
    return d,quality

def metrics(y,p,t):
    pred=p>=t
    return {'roc_auc':float(roc_auc_score(y,p)), 'average_precision':float(average_precision_score(y,p)),
        'brier':float(brier_score_loss(y,p)), 'precision_bad':float(precision_score(y,pred,zero_division=0)),
        'recall_bad':float(recall_score(y,pred,zero_division=0)), 'f1_bad':float(f1_score(y,pred,zero_division=0)),
        'confusion_matrix':confusion_matrix(y,pred,labels=[0,1]).tolist(),'n':len(y),'bad_rate':float(np.mean(y))}

def main(path):
    out=ROOT/'artifacts';out.mkdir(exist_ok=True)
    figs=ROOT/'reports/figures';figs.mkdir(parents=True,exist_ok=True)
    d,q=ingest(path); x=engineer(d); y=(d.flgGood=='Bad').astype(int)
    n=len(d);n1=int(n*.6);n2=int(n*.8)
    xt,xv,xs=x.iloc[:n1],x.iloc[n1:n2],x.iloc[n2:]
    yt,yv,ys=y.iloc[:n1],y.iloc[n1:n2],y.iloc[n2:]
    prep=ColumnTransformer([
      ('numeric',Pipeline([('impute',SimpleImputer(strategy='median',add_indicator=True)),('scale',StandardScaler())]),NUMERIC+DERIVED),
      ('category',Pipeline([('impute',SimpleImputer(strategy='most_frequent')),('encode',OneHotEncoder(handle_unknown='ignore',sparse_output=False))]),CATEGORICAL)])
    candidates={'baseline':DummyClassifier(strategy='prior'),
      'logistic':LogisticRegression(C=.3,max_iter=2000,random_state=42),
      'forest':RandomForestClassifier(n_estimators=150,max_depth=4,min_samples_leaf=12,random_state=42,n_jobs=1),
      'hist_gradient':HistGradientBoostingClassifier(max_iter=100,max_leaf_nodes=7,l2_regularization=5,random_state=42)}
    experiments=[];models={}
    for name,est in candidates.items():
        model=Pipeline([('prepare',prep),('classifier',est)])
        cv=cross_validate(model,xt,yt,cv=TimeSeriesSplit(3),scoring={'ap':'average_precision','auc':'roc_auc'},n_jobs=1)
        model.fit(xt,yt);models[name]=model
        experiments.append({'name':name,'cv_ap':float(np.mean(cv['test_ap'])),'cv_auc':float(np.mean(cv['test_auc'])),
            'fold_ap':cv['test_ap'].tolist(),'parameters':est.get_params()})
    winner=max([e for e in experiments if e['name']!='baseline'],key=lambda e:e['cv_ap'])['name']
    # Validation A calibrates; validation B chooses a threshold. Test is untouched.
    cut=len(xv)//2
    calibrated=CalibratedClassifierCV(FrozenEstimator(models[winner]),method='sigmoid')
    calibrated.fit(xv.iloc[:cut],yv.iloc[:cut])
    pv=calibrated.predict_proba(xv.iloc[cut:])[:,1]
    thresholds=np.arange(.1,.91,.01)
    def cost(t):
        tn,fp,fn,tp=confusion_matrix(yv.iloc[cut:],pv>=t,labels=[0,1]).ravel()
        return 5*fn+fp
    threshold=float(thresholds[np.argmin([cost(t) for t in thresholds])])
    ps=calibrated.predict_proba(xs)[:,1]; baseline=models['baseline'].predict_proba(xs)[:,1]
    test=metrics(ys,ps,threshold); base=metrics(ys,baseline,threshold)
    rng=np.random.default_rng(42); boot=[]
    for _ in range(1000):
        ix=rng.integers(0,len(ys),len(ys))
        if len(np.unique(ys.iloc[ix]))==2:boot.append(roc_auc_score(ys.iloc[ix],ps[ix]))
    test['auc_bootstrap_95']=np.quantile(boot,[.025,.975]).tolist()
    imp=permutation_importance(calibrated,xs,ys,n_repeats=10,random_state=42,scoring='roc_auc',n_jobs=1)
    importance=sorted([{'feature':c,'mean':float(m),'std':float(s)} for c,m,s in zip(x.columns,imp.importances_mean,imp.importances_std)],key=lambda r:r['mean'],reverse=True)
    ranges={c:{'min':float(xt[c].min()),'max':float(xt[c].max())} for c in NUMERIC}
    references={c:float(xt[c].median()) for c in NUMERIC}
    categories={c:sorted(xt[c].dropna().unique().tolist()) for c in CATEGORICAL}
    bins={}
    for c in NUMERIC:
        edges=np.unique(np.quantile(xt[c].dropna(),np.linspace(0,1,6)))
        edges[0]=-np.inf;edges[-1]=np.inf
        counts=np.histogram(xt[c],bins=edges)[0]
        bins[c]={'edges':[None if not np.isfinite(v) else float(v) for v in edges], 'proportions':(counts/counts.sum()).tolist()}
    artifact=out/'model.joblib';joblib.dump(calibrated,artifact)
    version=hashlib.sha256(artifact.read_bytes()).hexdigest()[:12]
    meta={'version':version,'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'winner':winner,
      'threshold':threshold,'threshold_cost_assumption':{'missed_bad':5,'flagged_good':1},
      'policy':'human_review_only','features':FEATURES,'reference_values':references,'ranges':ranges,
      'categories':categories,'drift_bins':bins,'test':test,'baseline':base,'experiments':experiments,
      'importance':importance,'quality':q,'split':{'train':n1,'calibration':cut,'threshold_validation':len(xv)-cut,'test':len(xs)},
      'split_date_ranges':{k:[str(v.application_when.min()),str(v.application_when.max())] for k,v in [('train',d.iloc[:n1]),('validation',d.iloc[n1:n2]),('test',d.iloc[n2:])]},
      'runtime':{'python':platform.python_version(),'sklearn':sklearn.__version__},
      'gate_reasons':['Historical data from 2010–2011','Approved-borrower selection bias','Unconfirmed join and outcome horizon','No prospective or fairness validation']}
    dump(out/'metadata.json',meta)
    snapshot=out/'versions'/version;snapshot.mkdir(parents=True,exist_ok=True)
    shutil.copy2(artifact,snapshot/'model.joblib');dump(snapshot/'metadata.json',meta)
    registry=json.loads((out/'registry.json').read_text()) if (out/'registry.json').exists() else {'versions':[]}
    if not any(v['version']==version for v in registry['versions']):
        registry['versions'].append({'version':version,'artifact':f'versions/{version}/model.joblib','sha256':meta['sha256'],'status':'research_only'})
    registry['champion']=version;dump(out/'registry.json',registry)
    dump(ROOT/'reports/data_validation.json',q)
    with (out/'experiments.jsonl').open('w') as f:
        for e in experiments:f.write(json.dumps(e,default=str)+'\n')
    plt.rcParams.update({'figure.figsize':(8,4.5),'axes.spines.top':False,'axes.spines.right':False,'font.size':11})
    def finish(name,title):
        plt.title(title,loc='left',weight='bold',pad=18);plt.tight_layout();plt.savefig(figs/name,dpi=180);plt.close()
    plt.bar(['Good','Bad'],[q['good'],q['bad']],color=['#2c9c95','#db7557']);plt.ylabel('First loans');finish('01_labels.png','Matched first-loan outcomes')
    fpr,tpr,_=roc_curve(ys,ps);plt.plot(fpr,tpr,color='#2c9c95',label=f"Test AUC {test['roc_auc']:.3f}");plt.plot([0,1],[0,1],'--',color='#888');plt.xlabel('False-positive rate');plt.ylabel('Bad-loan recall');plt.legend();finish('02_roc.png','Chronological holdout • ROC')
    precision,recall,_=precision_recall_curve(ys,ps);plt.plot(recall,precision,color='#2c9c95');plt.axhline(ys.mean(),ls='--',color='#888',label='Holdout bad rate');plt.xlabel('Bad-loan recall');plt.ylabel('Bad-loan precision');plt.legend();finish('03_precision_recall.png','Chronological holdout • precision and recall')
    frac,mean=calibration_curve(ys,ps,n_bins=5,strategy='quantile');plt.plot(mean,frac,'o-',color='#2c9c95');plt.plot([0,1],[0,1],'--',color='#888');plt.xlabel('Predicted bad probability');plt.ylabel('Observed bad rate');finish('04_calibration.png','Calibration • small holdout; interpret cautiously')
    top=importance[:8][::-1];plt.barh([i['feature'] for i in top],[i['mean'] for i in top],xerr=[i['std'] for i in top],color='#2c9c95');plt.xlabel('Decrease in test ROC-AUC after permutation');finish('05_importance.png','Global feature importance • predictive, not causal')
    from ml.eda import generate
    generate(d,q,meta,ROOT)
    print(json.dumps({'winner':winner,'test':test,'quality':{k:q[k] for k in ['matched_first_loans','bad','good','malformed_application_ids','unmatched_valid_applications']},'split':meta['split']}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--workbook',required=True);main(parser.parse_args().workbook)
