import os
from dataclasses import dataclass
from pathlib import Path
from sqlalchemy.engine import make_url
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
@dataclass
class Settings:
    database_url: str
    auth_secret: str
    origin: str
    production: bool
    hf_token: str
    hf_model: str
    hf_enabled: bool
    artifacts: Path

    @classmethod
    def load(cls):
        mode=os.getenv('APP_ENV','development')
        if mode not in {'development','production','test'}:raise RuntimeError('APP_ENV is invalid')
        db=os.getenv('DATABASE_URL','');secret=os.getenv('AUTH_SECRET','');origin=os.getenv('APP_ORIGIN','http://localhost:8000').rstrip('/')
        if not db:raise RuntimeError('DATABASE_URL is required')
        if len(secret)<32 or len(set(secret))<12:raise RuntimeError('AUTH_SECRET must be independently generated with at least 32 characters')
        try:url=make_url(db)
        except Exception:raise RuntimeError('DATABASE_URL is invalid') from None
        parsed=urlparse(origin)
        if parsed.scheme not in {'http','https'} or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username or '*' in origin:
            raise RuntimeError('APP_ORIGIN must be exactly one HTTP(S) origin')
        prod=mode=='production'
        if prod:
            if url.drivername!='postgresql+psycopg':raise RuntimeError('Production requires PostgreSQL via psycopg')
            if url.query.get('sslmode')!='verify-full' or not url.query.get('sslrootcert'):raise RuntimeError('Production database requires sslmode=verify-full and sslrootcert')
            if not url.username or not url.password:raise RuntimeError('Production database authentication is required')
            if not origin.startswith('https://') or '*' in origin:raise RuntimeError('Production APP_ORIGIN must be one explicit HTTPS origin')
        enabled=os.getenv('HF_ENABLED','false').lower()=='true';token=os.getenv('HF_TOKEN','');model=os.getenv('HF_MODEL','')
        if enabled and (not token or not model):raise RuntimeError('Enabled Hugging Face integration requires HF_TOKEN and HF_MODEL')
        return cls(db,secret,origin,prod,token,model,enabled,Path(os.getenv('ARTIFACT_DIR',str(ROOT/'artifacts'))))
