import os,secrets
import pytest
from fastapi.testclient import TestClient
from app.main import create_app

ORIGIN='http://localhost:8000'
@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('DATABASE_URL',os.getenv('TEST_DATABASE_URL','sqlite:///'+str(tmp_path/'test.db')))
    monkeypatch.setenv('AUTH_SECRET',secrets.token_urlsafe(48))
    monkeypatch.setenv('APP_ENV','test');monkeypatch.setenv('APP_ORIGIN',ORIGIN)
    monkeypatch.setenv('HF_ENABLED','false')
    app=create_app()
    # A real PostgreSQL test URL must point to a disposable database.
    from app.db import Base
    from sqlalchemy import create_engine
    if os.getenv('TEST_DATABASE_URL'):
        engine=create_engine(os.environ['TEST_DATABASE_URL']);Base.metadata.drop_all(engine);engine.dispose()
    with TestClient(app,headers={'Origin':ORIGIN}) as c:yield c

@pytest.fixture
def credentials():return {'email':'research-'+secrets.token_hex(5)+'@example.invalid','password':secrets.token_urlsafe(24)}
@pytest.fixture
def signed(client,credentials):
    response=client.post('/api/auth/signup',json=credentials);assert response.status_code==200
    client.headers['X-CSRF-Token']=response.json()['csrf_token']
    return client
@pytest.fixture
def application():
    return {'amount_requested':500,'loan_duration':6,'monthly_rent_amount':600,'monthly_income_amount':2400,
      'raw_l2c_score':650,'raw_FICO_telecom':570,'raw_FICO_retail':600,'raw_FICO_bank_card':640,'raw_FICO_money':580,
      'bank_account_direct_deposit':True,'payment_ach':True,'residence_duration':'1-2 years',
      'bank_account_duration':'1-2 years','payment_frequency':'Bi-weekly'}
