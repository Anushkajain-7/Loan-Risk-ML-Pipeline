import json
from pathlib import Path
import joblib,numpy as np,pandas as pd
from ml.features import FEATURES,EXCLUDED,engineer
from app.config import ROOT

def test_model_contract(application):
    metadata=json.loads((ROOT/'artifacts/metadata.json').read_text())
    assert not set(FEATURES)&set(EXCLUDED)
    assert sum(metadata['split'].values())==metadata['quality']['matched_first_loans']
    model=joblib.load(ROOT/'artifacts/model.joblib')
    x=engineer(pd.DataFrame([application]));before=model.predict_proba(x)
    application.update(email='unused@example.invalid',amount_approved=800,birth_date='2000-01-01')
    after=model.predict_proba(engineer(pd.DataFrame([application])))
    np.testing.assert_allclose(before,after)
    assert metadata['policy']=='human_review_only'

def test_artifact_integrity():
    import hashlib
    meta=json.loads((ROOT/'artifacts/metadata.json').read_text())
    assert hashlib.sha256((ROOT/'artifacts/model.joblib').read_bytes()).hexdigest()==meta['sha256']
