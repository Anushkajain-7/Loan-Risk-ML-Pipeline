"""Aggregate-only EDA. Sensitive source fields never leave this local process."""
import json
import numpy as np,pandas as pd,joblib
from sklearn.metrics import roc_auc_score,recall_score
from ml.features import NUMERIC,engineer

def generate(d,quality,meta,root):
    age=(d.application_when-d.birth_date).dt.total_seconds()/(365.2425*86400)
    month=d.application_when.dt.to_period('M').astype(str)
    eda={'ranges':d[NUMERIC].agg(['min','median','max']).to_dict(),
      'rent_exceeds_income':int((d.monthly_rent_amount>d.monthly_income_amount).sum()),
      'age_under_18':int((age<18).sum()),'age_min':float(age.min()),'age_max':float(age.max()),
      'monthly_counts':d.groupby(month).size().to_dict(),
      'monthly_bad_rate':d.groupby(month).flgGood.apply(lambda z:float((z=='Bad').mean())).to_dict(),
      'score_extreme_counts':quality['score_extreme_counts'],
      'retained_missing':d[['bank_account_duration']].isna().sum().to_dict()}
    start=sum(meta['split'][k] for k in ['train','calibration','threshold_validation'])
    test=d.iloc[start:];p=joblib.load(root/'artifacts/model.joblib').predict_proba(engineer(test))[:,1]
    y=(test.flgGood=='Bad').astype(int)
    groups=pd.cut(age.iloc[start:],[0,25,40,200],labels=['Under25','25to39','40plus'],right=False)
    eda['age_subgroup_audit']=[]
    for name in ['Under25','25to39','40plus']:
        mask=(groups==name).to_numpy();yg=y[mask];pg=p[mask]
        if mask.sum()>=20 and yg.nunique()==2:
            eda['age_subgroup_audit'].append({'age_band':name,'n':int(mask.sum()),'bad_rate':float(yg.mean()),
              'auc':float(roc_auc_score(yg,pg)),'recall_bad':float(recall_score(yg,pg>=meta['threshold']))})
        else:eda['age_subgroup_audit'].append({'age_band':name,'suppressed':'fewer than 20 observations or only one outcome class'})
    (root/'reports/eda.json').write_text(json.dumps(eda,indent=2,default=str))
    return eda
