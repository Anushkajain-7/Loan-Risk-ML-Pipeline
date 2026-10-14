# Security and private-file policy

Keep actual API tokens, database URLs/passwords, AUTH_SECRET, certificates/private keys, raw or processed borrower data, model artifacts, local databases, request logs, backups, and private upload files outside this public repository. The blank `.env.example` is a configuration template, not a place to save actual values.

The public report and chart images contain aggregate findings. Source and tests contain no default account or literal secret; tests generate passwords at runtime. The packaged pretrained model remains in the private project download and is not on public GitHub.

Before every commit:

```bash
python scripts/security_scan.py
git status --short
git diff --cached --stat
git diff --cached
```

Review staged content locally without pasting credentials into chat or logs. Never bypass ignore rules with `git add -f` for private files. `.gitignore` does not protect a file that is already tracked and is not a substitute for review or secret scanning.

If an actual secret is ever committed, revoke/rotate it immediately, remove it from the current tree, and use GitHub's documented sensitive-data removal process for history where appropriate. Changing repository visibility or deleting the latest file does not invalidate copied credentials.

For security findings, use GitHub private vulnerability reporting if enabled; otherwise contact the repository owner through a private channel. Do not put secrets, borrower information, or exploitable production details into a public issue.

This is a research model with an unconditional human-review policy. Production infrastructure, dependency CVEs, PostgreSQL integration, TLS, browser QA, and operational controls still require verification described in `reports/security_privacy_audit.md`.
