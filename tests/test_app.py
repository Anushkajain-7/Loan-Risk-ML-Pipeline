import json,secrets,time
import pytest
from sqlalchemy import select
from app.db import User,Session,Prediction
from app.config import Settings

def test_full_lifecycle(signed,application,credentials):
    result=signed.post('/api/predict',json=application)
    assert result.status_code==200
    data=result.json();assert 0<=data['bad_probability']<=1
    assert 'Human review' in data['recommendation']
    assert set(data)=={'reference','bad_probability','risk_band','recommendation','model_version','warnings','factors'}
    ref=data['reference'];assert signed.post(f'/api/predictions/{ref}/outcome',json={'outcome':'Bad'}).status_code==200
    history=signed.get('/api/predictions').json();assert history[0]['outcome']=='Bad'
    assert 'features' not in history[0] and 'user_id' not in history[0]
    assert signed.get('/api/monitoring').json()['labeled']==1
    assert signed.get('/api/model').status_code==200
    assert signed.delete('/api/predictions/'+ref).status_code==200
    assert signed.get('/api/predictions').json()==[]
    signed.post('/api/predict',json=application)
    assert signed.request('DELETE','/api/account',json={'password':credentials['password']}).status_code==200
    with signed.app.state.db() as db:
        assert not db.scalars(select(User)).all()
        assert not db.scalars(select(Session)).all()
        assert not db.scalars(select(Prediction)).all()
    assert signed.get('/api/auth/me').status_code==401

@pytest.mark.parametrize('method,path',[('GET','/api/predictions'),('GET','/api/monitoring'),('GET','/api/model'),('GET','/api/report'),('GET','/figures/01_labels.png'),('POST','/api/predict'),('POST','/api/predict/batch'),('DELETE','/api/account'),('DELETE','/api/predictions/random'),('POST','/api/predictions/random/outcome'),('POST','/api/predictions/random/explain'),('POST','/api/auth/logout')])
def test_auth_required(client,method,path):
    assert client.request(method,path,json={}).status_code==401

def test_ownership_on_every_id_endpoint(signed,application):
    from fastapi.testclient import TestClient
    ref=signed.post('/api/predict',json=application).json()['reference']
    other=TestClient(signed.app,headers={'Origin':'http://localhost:8000'})
    res=other.post('/api/auth/signup',json={'email':'second-'+secrets.token_hex(4)+'@example.invalid','password':secrets.token_urlsafe(24)})
    other.headers['X-CSRF-Token']=res.json()['csrf_token']
    assert other.get('/api/predictions').json()==[]
    assert other.delete('/api/predictions/'+ref).status_code==404
    assert other.post('/api/predictions/'+ref+'/outcome',json={'outcome':'Good'}).status_code==404
    # Provider disabled is checked before ownership, and exposes no record.
    assert other.post('/api/predictions/'+ref+'/explain',json={'consent':True}).status_code==503

def test_hashed_password_and_session(signed,credentials):
    with signed.app.state.db() as db:
        user=db.scalar(select(User));sess=db.scalar(select(Session))
        assert user.password_hash.startswith('$argon2id$')
        assert credentials['password'] not in user.password_hash
        assert sess.token_hash!=signed.cookies.get('session')
    me=signed.get('/api/auth/me').json();assert set(me)=={'authenticated','csrf_token'}

def test_expired_malformed_session(signed):
    with signed.app.state.db() as db:
        sess=db.scalar(select(Session));sess.expires=int(time.time())-1;db.commit()
    assert signed.get('/api/auth/me').status_code==401
    signed.cookies.clear();signed.cookies.set('session','tampered')
    assert signed.get('/api/auth/me').status_code==401

def test_login_and_rate_limit(client,credentials):
    res=client.post('/api/auth/signup',json=credentials);assert res.status_code==200
    client.cookies.clear()
    res=client.post('/api/auth/login',json=credentials);assert res.status_code==200
    assert 'HttpOnly' in res.headers['set-cookie'] and 'SameSite=strict' in res.headers['set-cookie']
    assert 'Secure' not in res.headers['set-cookie'] # localhost development mode
    wrong={**credentials,'password':secrets.token_urlsafe(24)}
    for _ in range(4):assert client.post('/api/auth/login',json=wrong).status_code==401
    assert client.post('/api/auth/login',json=wrong).status_code==429

def test_csrf_and_origin(signed,application):
    assert signed.post('/api/predict',json=application,headers={'X-CSRF-Token':'invalid'}).status_code==403
    assert signed.post('/api/predict',json=application,headers={'Origin':'https://attacker.invalid'}).status_code==403
    signed.headers.pop('Origin');assert signed.post('/api/predict',json=application).status_code==403

@pytest.mark.parametrize('name,value',[('monthly_income_amount',0),('raw_FICO_money',-1),('payment_frequency','<script>alert(1)</script>'),('role','admin'),('email','stolen@example.invalid')])
def test_validation_and_role_injection(signed,application,name,value):
    res=signed.post('/api/predict',json={**application,name:value});assert res.status_code==422
    assert value not in res.json().values()
    assert 'traceback' not in res.text and 'input' not in res.json()

def test_signup_role_injection(client,credentials):
    assert client.post('/api/auth/signup',json={**credentials,'role':'admin'}).status_code==422

def test_sql_injection_login(client):
    res=client.post('/api/auth/login',json={'email':"a'OR'1'='1@example.invalid",'password':secrets.token_urlsafe(24)})
    assert res.status_code in {401,422}

def test_batch_bounds(signed,application):
    res=signed.post('/api/predict/batch',json={'applications':[application,application]});assert res.status_code==200 and len(res.json())==2
    assert signed.post('/api/predict/batch',json={'applications':[application]*51}).status_code==422

def test_no_internal_exposure(client):
    for path in ['/.env','/.git/config','/docs','/redoc','/openapi.json','/debug','/test','/seed-data','/admin-backdoor','/admin','/assets/..%2F.env']:
        assert client.get(path).status_code==404
    assert client.get('/health').json()=={'status':'ok'}
    assert client.get('/').status_code==200
    assert client.get('/assets/app.js').status_code==200

def test_headers_and_cors(client):
    for path in ['/','/health','/not-found','/api/auth/me']:
        res=client.get(path)
        assert res.headers['x-content-type-options']=='nosniff'
        assert res.headers['x-frame-options']=='DENY'
        assert '31536000' in res.headers['strict-transport-security']
        assert "script-src 'self'" in res.headers['content-security-policy']
        assert res.headers['cache-control']=='no-store'
    res=client.options('/api/predict',headers={'Origin':'https://attacker.invalid','Access-Control-Request-Method':'POST'})
    assert res.status_code==400 and 'access-control-allow-origin' not in res.headers

def test_body_size(client):
    assert client.post('/api/auth/login',content='x'*65537).status_code==413

def test_out_of_range(signed,application):
    res=signed.post('/api/predict',json={**application,'amount_requested':9000})
    assert res.status_code==200 and res.json()['risk_band']=='outside_training_range'

def test_no_pii_logs(signed,application,credentials,caplog):
    signed.post('/api/predict',json={**application,'email':credentials['email']})
    signed.post('/api/auth/login',json={**credentials,'password':secrets.token_urlsafe(24)})
    assert credentials['email'] not in caplog.text and credentials['password'] not in caplog.text

def test_provider_minimization(signed,application,monkeypatch):
    import huggingface_hub
    from types import SimpleNamespace
    signed.app.state.settings.hf_enabled=True;signed.app.state.settings.hf_token=secrets.token_urlsafe(32);signed.app.state.settings.hf_model='test-model'
    ref=signed.post('/api/predict',json=application).json()['reference']
    captured={}
    class Stub:
        def __init__(self,**kwargs):pass
        def chat_completion(self,**kwargs):
            captured.update(kwargs);return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Human review required.'))])
    monkeypatch.setattr(huggingface_hub,'InferenceClient',Stub)
    assert signed.post(f'/api/predictions/{ref}/explain',json={'consent':False}).status_code==400
    assert signed.post(f'/api/predictions/{ref}/explain',json={'consent':True}).status_code==200
    message=json.loads(captured['messages'][1]['content'])
    assert set(message)=={'risk_band','feature_names'} and ref not in json.dumps(message)
    # Active provider still verifies ownership.
    assert signed.post('/api/predictions/nonowned/explain',json={'consent':True}).status_code==404

def test_critical_config(monkeypatch):
    monkeypatch.setenv('DATABASE_URL','');monkeypatch.setenv('AUTH_SECRET',secrets.token_urlsafe(48))
    with pytest.raises(RuntimeError,match='DATABASE_URL'):Settings.load()
    monkeypatch.setenv('DATABASE_URL','sqlite://');monkeypatch.setenv('AUTH_SECRET','')
    with pytest.raises(RuntimeError,match='AUTH_SECRET'):Settings.load()
    monkeypatch.setenv('AUTH_SECRET',secrets.token_urlsafe(48));monkeypatch.setenv('APP_ENV','production')
    with pytest.raises(RuntimeError,match='PostgreSQL'):Settings.load()
    monkeypatch.setenv('DATABASE_URL','postgresql+psycopg://')
    with pytest.raises(RuntimeError,match='sslmode'):Settings.load()
    monkeypatch.setenv('APP_ENV','test');monkeypatch.setenv('HF_ENABLED','true');monkeypatch.setenv('HF_TOKEN','');monkeypatch.setenv('HF_MODEL','')
    with pytest.raises(RuntimeError,match='Hugging Face'):Settings.load()

def test_signup_rate_limit(client):
    for _ in range(3):
        result=client.post('/api/auth/signup',json={'email':secrets.token_hex(5)+'@example.invalid','password':secrets.token_urlsafe(24)})
        assert result.status_code==200
    assert client.post('/api/auth/signup',json={'email':secrets.token_hex(5)+'@example.invalid','password':secrets.token_urlsafe(24)}).status_code==429

def test_secure_cookie_production_flag(client,credentials):
    client.app.state.settings.production=True
    res=client.post('/api/auth/signup',json=credentials)
    assert res.status_code==200
    assert 'Secure' in res.headers['set-cookie'] and 'HttpOnly' in res.headers['set-cookie'] and 'SameSite=strict' in res.headers['set-cookie']

def test_error_redaction(signed,application,monkeypatch,credentials,caplog):
    def broken(*args,**kwargs):raise RuntimeError(credentials['email']+' '+credentials['password'])
    monkeypatch.setattr(signed.app.state.model,'predict_proba',broken)
    res=signed.post('/api/predict',json=application)
    assert res.status_code==500 and res.json()['message']=='Unable to complete request'
    assert credentials['email'] not in res.text+caplog.text and credentials['password'] not in res.text+caplog.text
    assert res.headers['x-frame-options']=='DENY'

def test_monitoring_at_sample_minimum(signed,application):
    from app.db import Prediction
    import uuid
    version=signed.app.state.meta['version']
    with signed.app.state.db() as db:
        owner=db.scalar(select(User)).id
        for i in range(20):db.add(Prediction(id=str(uuid.uuid4()),user_id=owner,features=application,probability=.3 if i%2 else .7,band='uncertain',version=version,outcome=int(i%2==0),reasons=[]))
        db.commit()
    m=signed.get('/api/monitoring').json();assert len(m['psi'])==9 and m['performance']['auc']==1

def test_prediction_limit(signed,application):
    from app.main import digest
    from app.db import Limit
    now=int(time.time());owner=None
    with signed.app.state.db() as db:
        owner=db.scalar(select(User)).id
        key=digest(signed.app.state.settings.auth_secret,f'predict:{owner}:{now//60}')
        db.add(Limit(key=key,count=30,expires=now+60));db.commit()
    assert signed.post('/api/predict',json=application).status_code==429

def test_provider_timeout(signed,application,monkeypatch):
    import huggingface_hub
    signed.app.state.settings.hf_enabled=True;signed.app.state.settings.hf_token=secrets.token_urlsafe(32);signed.app.state.settings.hf_model='test-model'
    ref=signed.post('/api/predict',json=application).json()['reference']
    class Unavailable:
        def __init__(self,**kwargs):pass
        def chat_completion(self,**kwargs):raise TimeoutError('private provider details')
    monkeypatch.setattr(huggingface_hub,'InferenceClient',Unavailable)
    res=signed.post(f'/api/predictions/{ref}/explain',json={'consent':True})
    assert res.status_code==503 and 'private provider details' not in res.text

def test_account_deletion_bad_password(signed):
    assert signed.request('DELETE','/api/account',json={'password':secrets.token_urlsafe(24)}).status_code==401
    assert signed.get('/api/auth/me').status_code==200

def test_logout_revokes(signed):
    cookie=signed.cookies.get('session')
    assert signed.post('/api/auth/logout',json={}).status_code==200
    signed.cookies.set('session',cookie)
    assert signed.get('/api/auth/me').status_code==401
