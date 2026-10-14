"""Local launcher with private .env loading, no value output and no debug logs."""
import os
from pathlib import Path
import uvicorn
if __name__=='__main__':
    for line in Path('.env').read_text().splitlines():
        if line and not line.startswith('#'):
            key,value=line.split('=',1);os.environ.setdefault(key,value)
    uvicorn.run('app.main:create_app',factory=True,host='127.0.0.1',port=8000,access_log=False,proxy_headers=False)
