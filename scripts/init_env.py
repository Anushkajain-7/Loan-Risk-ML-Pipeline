"""Generate local development secrets; never prints their values."""
import argparse,os,secrets
from pathlib import Path
from urllib.parse import quote

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--sqlite',action='store_true');args=parser.parse_args()
    target=Path('.env')
    if target.exists():raise SystemExit('Existing .env preserved; edit it intentionally.')
    user='loanlens_'+secrets.token_hex(4);password=secrets.token_urlsafe(36)
    app_user='app_'+secrets.token_hex(4);app_password=secrets.token_urlsafe(36)
    db='sqlite:///./loanlens.db' if args.sqlite else f'postgresql+psycopg://{app_user}:{quote(app_password,safe="")}@db:5432/loanlens'
    text=f'APP_ENV=development\nAPP_ORIGIN=http://localhost:8000\nDATABASE_URL={db}\nAUTH_SECRET={secrets.token_urlsafe(48)}\nPOSTGRES_USER={user}\nPOSTGRES_PASSWORD={password}\nAPP_DB_USER={app_user}\nAPP_DB_PASSWORD={app_password}\nPOSTGRES_DB=loanlens\nHF_ENABLED=false\nHF_TOKEN=\nHF_MODEL=\n'
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:f.write(text)
    print('Created a private local .env with independently generated secrets.')
if __name__=='__main__':main()
