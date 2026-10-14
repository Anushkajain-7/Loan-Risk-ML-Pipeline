import hashlib,hmac,json,logging,secrets,time,uuid
from contextlib import asynccontextmanager
from pathlib import Path
import joblib,numpy as np,pandas as pd
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError,InvalidHashError,VerificationError
from fastapi import FastAPI,Request,Depends,HTTPException,Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse,FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy import select,delete,update
from sqlalchemy.exc import IntegrityError
from app.config import Settings,ROOT
from app.db import Base,User,Session,Prediction,Limit,database
from app.schemas import Credentials,Confirm,Application,Batch,Feedback,ExplainRequest,PredictionOut
from ml.features import FEATURES,NUMERIC,engineer

log=logging.getLogger('loanrisk')
ph=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2)
def digest(secret,value):return hmac.new(secret.encode(),value.encode(),hashlib.sha256).hexdigest()
def verify(hashed,password):
    try:return ph.verify(hashed,password)
    except (VerifyMismatchError,InvalidHashError,VerificationError):return False

def create_app():
    settings=Settings.load()
    engine,db=database(settings.database_url)
    @asynccontextmanager
    async def lifespan(app):
        meta=json.loads((settings.artifacts/'metadata.json').read_text())
        artifact=settings.artifacts/'model.joblib'
        if hashlib.sha256(artifact.read_bytes()).hexdigest()!=meta['sha256']:raise RuntimeError('Model artifact integrity check failed')
        if meta['runtime']['sklearn']!=__import__('sklearn').__version__:raise RuntimeError('Model scikit-learn version mismatch; retrain with this runtime')
        app.state.model=joblib.load(artifact);app.state.meta=meta
        app.state.dummy_hash=ph.hash(secrets.token_urlsafe(32))
        Base.metadata.create_all(engine)
        try:
            with db() as s:s.execute(select(User).limit(1))
        except Exception:raise RuntimeError('Database unavailable; verify connectivity and TLS configuration privately') from None
        yield
        engine.dispose()
    app=FastAPI(title='LoanLens',lifespan=lifespan,debug=False,docs_url=None,redoc_url=None,openapi_url=None)
    app.state.db=db;app.state.settings=settings
    app.add_middleware(CORSMiddleware,allow_origins=[settings.origin],allow_credentials=True,allow_methods=['GET','POST','DELETE'],allow_headers=['Content-Type','X-CSRF-Token'])
    def error(request,status,message):
        return JSONResponse({'message':message,'correlation_id':getattr(request.state,'correlation_id',str(uuid.uuid4()))},status_code=status)
    @app.exception_handler(RequestValidationError)
    async def invalid(request,exc):return error(request,422,'Request does not match the input contract')
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request,exc):return error(request,exc.status_code,exc.detail if isinstance(exc.detail,str) else 'Request rejected')
    @app.middleware('http')
    async def guard(request,call_next):
        request.state.correlation_id=str(uuid.uuid4())
        try:
            if request.method in {'POST','DELETE','PUT','PATCH'}:
                if request.headers.get('origin')!=settings.origin:
                    response=error(request,403,'Origin rejected')
                else:
                    chunks=[];size=0
                    async for chunk in request.stream():
                        size+=len(chunk)
                        if size>65536:break
                        chunks.append(chunk)
                    if size>65536:response=error(request,413,'Request too large')
                    else:
                        request._body=b''.join(chunks)
                        response=await call_next(request)
            else:response=await call_next(request)
        except Exception as exc:
            # Exception payloads, query parameters, bodies and tracebacks may contain PII.
            log.error('request_failed correlation_id=%s class=%s',request.state.correlation_id,type(exc).__name__)
            response=error(request,500,'Unable to complete request')
        for k,v in {'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY',
          'Strict-Transport-Security':'max-age=31536000; includeSubDomains',
          'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
          'Referrer-Policy':'no-referrer','Permissions-Policy':'camera=(), microphone=(), geolocation=()',
          'Cache-Control':'no-store','X-Correlation-ID':request.state.correlation_id}.items():response.headers[k]=v
        return response

    def limit(request,bucket,maximum,seconds,identity=None):
        # HMAC pseudonymizes the network identifier. Never trust X-Forwarded-For.
        now=int(time.time());window=now//seconds
        identity=identity or (request.client.host if request.client else 'unknown')
        key=digest(settings.auth_secret,f'{bucket}:{identity}:{window}')
        with db() as s:
            try:
                s.add(Limit(key=key,count=0,expires=(window+1)*seconds));s.commit()
            except IntegrityError:s.rollback()
            result=s.execute(update(Limit).where(Limit.key==key,Limit.count<maximum).values(count=Limit.count+1));s.commit()
            if result.rowcount!=1:raise HTTPException(429,'Rate limit exceeded')

    def auth(request:Request):
        token=request.cookies.get('session','')
        with db() as s:
            session=s.get(Session,digest(settings.auth_secret,token)) if token else None
            if not session or session.expires<int(time.time()):raise HTTPException(401,'Authentication required')
            if request.method!='GET' and not secrets.compare_digest(request.headers.get('x-csrf-token',''),session.csrf):raise HTTPException(403,'CSRF check failed')
            limit(request,'authenticated_api',120,60,session.user_id)
            return session.user_id

    def issue(s,user_id,response):
        token=secrets.token_urlsafe(48);csrf=secrets.token_urlsafe(32)
        s.add(Session(token_hash=digest(settings.auth_secret,token),user_id=user_id,csrf=csrf,expires=int(time.time())+3600));s.commit()
        response.set_cookie('session',token,httponly=True,secure=settings.production,samesite='strict',max_age=3600,path='/')
        return {'authenticated':True,'csrf_token':csrf}

    @app.post('/api/auth/signup')
    def signup(payload:Credentials,request:Request,response:Response):
        limit(request,'signup',3,3600)
        with db() as s:
            user=User(id=str(uuid.uuid4()),email=payload.email,password_hash=ph.hash(payload.password))
            s.add(user)
            try:s.commit()
            except IntegrityError:s.rollback();raise HTTPException(400,'Unable to create account')
            return issue(s,user.id,response)

    @app.post('/api/auth/login')
    def login(payload:Credentials,request:Request,response:Response):
        limit(request,'login',5,60)
        limit(request,'login_account',10,3600,payload.email)
        with db() as s:
            user=s.scalar(select(User).where(User.email==payload.email))
            if not verify(user.password_hash if user else app.state.dummy_hash,payload.password):raise HTTPException(401,'Invalid credentials')
            return issue(s,user.id,response)

    @app.get('/api/auth/me')
    def me(request:Request,user_id=Depends(auth)):
        with db() as s:
            sess=s.get(Session,digest(settings.auth_secret,request.cookies['session']))
            return {'authenticated':True,'csrf_token':sess.csrf}

    @app.post('/api/auth/logout')
    def logout(request:Request,response:Response,user_id=Depends(auth)):
        with db() as s:s.execute(delete(Session).where(Session.token_hash==digest(settings.auth_secret,request.cookies['session'])));s.commit()
        response.delete_cookie('session',path='/',secure=settings.production,httponly=True,samesite='strict')
        return {'deleted':True}

    @app.delete('/api/account')
    def remove_account(payload:Confirm,request:Request,response:Response,user_id=Depends(auth)):
        limit(request,'delete',5,60)
        with db() as s:
            user=s.get(User,user_id)
            if not verify(user.password_hash,payload.password):raise HTTPException(401,'Invalid credentials')
            s.delete(user);s.commit()
        response.delete_cookie('session',path='/',secure=settings.production,httponly=True,samesite='strict')
        return {'deleted':True}

    def score(payload,user_id,s):
        meta=app.state.meta;data=payload.model_dump();x=engineer(pd.DataFrame([data]))
        probability=float(app.state.model.predict_proba(x)[0,1]);warnings=[]
        for c,r in meta['ranges'].items():
            if not r['min']<=data[c]<=r['max']:warnings.append(f'{c}: outside the training range')
        if data['monthly_rent_amount']>data['monthly_income_amount']:warnings.append('Rent exceeds reported income; verify affordability')
        band='outside_training_range' if warnings else ('lower' if probability<meta['threshold']-.1 else 'higher' if probability>meta['threshold']+.1 else 'uncertain')
        factors=[]
        for c in NUMERIC:
            changed=data.copy();changed[c]=meta['reference_values'][c]
            reference_probability=float(app.state.model.predict_proba(engineer(pd.DataFrame([changed])))[0,1])
            factors.append({'feature':c,'probability_difference':round(probability-reference_probability,4)})
        factors=sorted(factors,key=lambda f:abs(f['probability_difference']),reverse=True)[:3]
        ref=str(uuid.uuid4())
        s.add(Prediction(id=ref,user_id=user_id,features=data,probability=probability,band=band,version=meta['version'],reasons=factors))
        return PredictionOut(reference=ref,bad_probability=round(probability,4),risk_band=band,
          recommendation='Human review required — research model, no automated approval',model_version=meta['version'],
          warnings=warnings+meta['gate_reasons'],factors=factors)

    @app.post('/api/predict',response_model=PredictionOut)
    def predict(payload:Application,request:Request,user_id=Depends(auth)):
        limit(request,'predict',30,60,user_id)
        with db() as s:result=score(payload,user_id,s);s.commit();return result

    @app.post('/api/predict/batch',response_model=list[PredictionOut])
    def batch(payload:Batch,request:Request,user_id=Depends(auth)):
        limit(request,'batch',2,60,user_id)
        with db() as s:results=[score(p,user_id,s) for p in payload.applications];s.commit();return results

    def owned(s,ref,user_id):
        prediction=s.scalar(select(Prediction).where(Prediction.id==ref,Prediction.user_id==user_id))
        if not prediction:raise HTTPException(404,'Prediction not found')
        return prediction

    @app.get('/api/predictions')
    def history(user_id=Depends(auth)):
        with db() as s:
            rows=s.scalars(select(Prediction).where(Prediction.user_id==user_id).order_by(Prediction.created.desc()).limit(50))
            return [{'reference':p.id,'bad_probability':round(p.probability,4),'risk_band':p.band,'created':p.created,'outcome':None if p.outcome is None else 'Bad' if p.outcome else 'Good'} for p in rows]

    @app.delete('/api/predictions/{ref}')
    def remove_prediction(ref:str,user_id=Depends(auth)):
        with db() as s:s.delete(owned(s,ref,user_id));s.commit()
        return {'deleted':True}

    @app.post('/api/predictions/{ref}/outcome')
    def outcome(ref:str,payload:Feedback,request:Request,user_id=Depends(auth)):
        limit(request,'outcome',30,60,user_id)
        with db() as s:p=owned(s,ref,user_id);p.outcome=int(payload.outcome=='Bad');s.commit()
        return {'recorded':True,'source':'user_reported_unverified'}

    @app.post('/api/predictions/{ref}/explain')
    def explain(ref:str,payload:ExplainRequest,request:Request,user_id=Depends(auth)):
        limit(request,'explain',5,60,user_id)
        if not payload.consent:raise HTTPException(400,'Explicit consent required')
        if not settings.hf_enabled:raise HTTPException(503,'Optional explanation provider is disabled')
        with db() as s:p=owned(s,ref,user_id);band=p.band;names=[r['feature'] for r in p.reasons]
        # Only coarse band and feature NAMES leave this backend. No applicant values or IDs.
        from huggingface_hub import InferenceClient
        try:
            result=InferenceClient(token=settings.hf_token,timeout=15).chat_completion(model=settings.hf_model,
              messages=[{'role':'system','content':'Explain a research-only credit-risk indicator in plain language. Do not recommend approval or denial, claim causality, or invent facts. Always state human review is required.'},
                {'role':'user','content':json.dumps({'risk_band':band,'feature_names':names})}],max_tokens=180)
            return {'explanation':result.choices[0].message.content,'source':'Hugging Face; informational only'}
        except Exception:raise HTTPException(503,'Explanation provider unavailable')

    @app.get('/api/monitoring')
    def monitor(user_id=Depends(auth)):
        with db() as s:rows=list(s.scalars(select(Prediction).where(Prediction.user_id==user_id)))
        labeled=[p for p in rows if p.outcome is not None];psi={}
        if len(rows)>=20:
            for c,spec in app.state.meta['drift_bins'].items():
                edges=[-np.inf if i==0 else np.inf if i==len(spec['edges'])-1 else v for i,v in enumerate(spec['edges'])]
                observed=np.histogram([p.features[c] for p in rows],bins=edges)[0]/len(rows)
                a=np.clip(observed,.001,1);b=np.clip(spec['proportions'],.001,1)
                psi[c]=float(np.sum((a-b)*np.log(a/b)))
        performance=None
        if len(labeled)>=20 and len({p.outcome for p in labeled})==2:
            from sklearn.metrics import roc_auc_score,brier_score_loss
            performance={'auc':float(roc_auc_score([p.outcome for p in labeled],[p.probability for p in labeled])),
              'brier':float(brier_score_loss([p.outcome for p in labeled],[p.probability for p in labeled]))}
        return {'requests':len(rows),'labeled':len(labeled),'psi':psi,'performance':performance,
            'alerts':[c for c,v in psi.items() if v>.2], 'scope':'Your account only; labels are unverified; PSI requires 20 records; no automatic retraining'}

    @app.get('/api/model')
    def model_info(user_id=Depends(auth)):
        m=app.state.meta
        return {k:m[k] for k in ['version','winner','threshold','policy','test','baseline','split','gate_reasons']}

    @app.get('/api/report')
    def report(user_id=Depends(auth)):
        return FileResponse(ROOT/'reports/project_report.html')

    @app.get('/api/report.css')
    def report_css(user_id=Depends(auth)):
        return FileResponse(ROOT/'reports/report.css')

    @app.get('/health')
    def health():return {'status':'ok'}

    @app.get('/')
    def index():return FileResponse(ROOT/'frontend/index.html')
    @app.get('/assets/{name}')
    def asset(name:str):
        if name not in {'app.js','style.css'}:raise HTTPException(404,'Asset not found')
        return FileResponse(ROOT/'frontend'/name)
    @app.get('/figures/{name}')
    @app.get('/api/figures/{name}')
    def figure(name:str,user_id=Depends(auth)):
        if name not in {'01_labels.png','02_roc.png','03_precision_recall.png','04_calibration.png','05_importance.png'}:raise HTTPException(404,'Figure not found')
        return FileResponse(ROOT/'reports/figures'/name)
    return app
