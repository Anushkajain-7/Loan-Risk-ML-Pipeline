"""Heuristic whole-project scan. Reports locations/types, never values."""
import ast,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PATTERNS=[('provider_key',re.compile(r'(?:hf_[A-Za-z0-9]{25,}|sk-[A-Za-z0-9]{25,}|AKIA[A-Z0-9]{16})')),
 ('credential_uri',re.compile(r'(?:postgres(?:ql)?|mongodb(?:\+srv)?)://[^\s:@]+:[^\s@]+@')),
 ('private_key',re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),
 ('sensitive_public_env',re.compile(r'(?:NEXT_PUBLIC_|REACT_APP_)(?:[A-Z_]*(?:SECRET|PASSWORD|PRIVATE|SERVICE_ROLE|TOKEN))'))]
def scan():
    findings=[];count=0
    for p in ROOT.rglob('*'):
        if not p.is_file() or any(x in p.parts for x in ['.git','__pycache__','.pytest_cache','.venv','certs']):continue
        if p.suffix not in {'.py','.js','.html','.css','.md','.yaml','.json','.jsonl','.txt','.sh','.xml'} and p.name not in {'.env.example','Dockerfile','Caddyfile','.gitignore','.dockerignore'}:continue
        count+=1;text=p.read_text(errors='replace')
        for kind,pattern in PATTERNS:
            for match in pattern.finditer(text):findings.append({'file':str(p.relative_to(ROOT)),'line':text[:match.start()].count('\n')+1,'type':kind})
        if p.suffix=='.py':
            tree=ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node,(ast.Assign,ast.AnnAssign)):
                    targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                    if any(isinstance(t,ast.Name) and re.search(r'^(?:password|auth_secret|api_key|hf_token|client_secret)$',t.id,re.I) for t in targets):
                        v=node.value
                        if isinstance(v,ast.Constant) and isinstance(v.value,str) and v.value:findings.append({'file':str(p.relative_to(ROOT)),'line':node.lineno,'type':'literal_secret_assignment'})
    result={'scanned_text_files':count,'findings':findings,'status':'PASS' if not findings else 'FAIL',
      'limits':'Heuristic source/config scan only. No inherited Git history, binary secret detector, or CVE database was available.'}
    (ROOT/'reports/secret_scan.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
    return bool(findings)
if __name__=='__main__':raise SystemExit(scan())
