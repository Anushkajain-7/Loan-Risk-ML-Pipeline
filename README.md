# LoanLens - loan-risk research application

A connected FastAPI web app, PostgreSQL database design, reproducible scikit-learn pipeline, chronological evaluation, image charts, account-only monitoring, and security/privacy audit. **Research use only: every assessment requires human review.** This project cannot establish who should receive a loan today from the supplied data alone.

## Public repository and private setup

This repository publishes reviewed source, tests, deployment definitions, documentation, and aggregate charts/reports. Actual `.env` files, borrower datasets, trained models/metadata, database files, logs, certificates, backups, and uploads are excluded. See `SECURITY.md` and `.gitignore`.

**Before starting the app or running model/API tests from a clone**, restore your authorized private `artifacts/` from the project download, or train locally using the privately held workbook. The public repository does not ship `model.joblib` or `metadata.json`; without them the app intentionally cannot start. Keep all generated artifacts private.

```bash
git clone https://github.com/Anushkajain-7/Loan-Risk-ML-Pipeline.git
cd Loan-Risk-ML-Pipeline
```

To train locally first, create a Python 3.12 virtual environment, install `requirements.txt`, put the workbook in ignored `data/raw/`, and follow **Reproduce training** below. Copying artifacts from the private project package is an alternative that does not require retraining.

## Findings from the supplied workbook

- 647 applications; 1,285 loan outcomes; 1,269 distinct outcome customers.
- Normalize mixed-type customer IDs, match the loan-ID prefix, and use first-loan suffix `-01`: 641 matched first loans (352 Bad, 289 Good).
- Exclude two malformed application IDs and four valid unmatched applications. Do not invent labels. Sixteen repeat-loan outcomes are excluded; three repeat customers have different first/second outcomes.
- Selected random forest: test ROC-AUC **0.621**, average precision **0.650**, Brier **0.239** on **129** later applications. Bootstrap ROC-AUC interval **0.522-0.713**, conditional on this sample and fixed model.
- At the illustrative validation-selected threshold **0.28**, Bad recall is **100%** but **62/64 good loans are flagged**. Specificity is only **3.1%**. This threshold is unsuitable for automatic decisions.
- Historical 2010-2011 approved borrowers are not representative of current applicants. Join interpretation, outcome definition/horizon, score semantics, currency, and duration units require source-owner confirmation.

## Run locally with PostgreSQL (recommended)

Prerequisites: Docker with Docker Compose, Python 3.12 for the environment generator.

```bash
cd Loan-Risk-ML-Pipeline
python scripts/init_env.py
docker compose up --build -d
```

Open `http://localhost:8000`, create your own account with a new 12+ character password, and click **Load synthetic example**. There are no default accounts. Database credentials and the signing secret are generated independently into an ignored `.env`, without printing them. The database port is never published. The database app role is not a superuser. Account email is for login; applicant identities are never collected by the assessment form.

For a small local demo without Docker:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/init_env.py --sqlite
python scripts/run_local.py
```

SQLite is a development/test adapter; production startup rejects it. If `.env` already exists, the generator preserves it. Use a separate checkout/directory for the other demo mode, or intentionally edit the existing file. Do not commit or send the environment file.

## Reproduce training

The public repository intentionally omits the original workbook, borrower identities, and trained model artifacts. Place your supplied workbook in the ignored `data/raw/` directory. The private project package contains the pretrained artifacts, so its original local startup instructions still apply.

```bash
python -m ml.train --workbook 'data/raw/AssessmentDataScientist(2).xlsx'
python scripts/build_report.py --no-pdf
```

Train in a private workspace. This reads only the named sheets, validates IDs and join cardinality, handles missing values inside folds, engineers request/income and rent/income ratios, imputes, scales numeric columns, one-hot encodes categories, and compares baseline, logistic regression, forest, and histogram gradient boosting. Numeric scaling is shared across models; it matters for logistic regression but is not required by tree models. There is no SMOTE: the matched population is not severely imbalanced.

The earliest 384 records train models and support three expanding-window CV folds. The next 64 calibrate the frozen selected model; the following 64 select a threshold under an assumed 5:1 missed-Bad/flagged-Good cost. The last 129 are held out. Test labels never select the model, calibrator, or threshold. Model selection uses mean CV average precision. Threshold assumptions are illustrative, not verified financial costs. Label availability dates are absent, so chronology alone cannot prove point-in-time label availability.

`artifacts/experiments.jsonl` records parameters and CV metrics. `registry.json` points to a versioned research artifact; version snapshots preserve model, metadata, and source hash. This is a local file registry, not a hosted MLflow registry. Retraining never happens inside a request. Retrain privately, review new evidence, then release the entire version as a new deployment; do not replace an artifact underneath a running server. Lifespan loads the model once, checks its SHA-256 and scikit-learn version, and reuses it. Joblib is unsafe for untrusted input: only load these operator-controlled build artifacts. The checksum detects accidental changes; it is not an authenticity signature.

## API and frontend

Same-origin frontend files are served by FastAPI, eliminating cross-service URL configuration. There is no mocked prediction logic. The browser sends JSON to the backend and stores no account/applicant data in localStorage, sessionStorage, or IndexedDB. Session cookies are HttpOnly; CSRF tokens are held in memory.

| API | Protection and purpose |
| --- | --- |
| `POST /api/auth/signup`, `/login` | Origin required; database-backed IP/account rate limits |
| `GET /api/auth/me` | Active session; returns only authenticated state and CSRF token |
| `POST /api/auth/logout` | Session + CSRF + origin; invalidates current session |
| `DELETE /api/account` | Session + CSRF + origin + password; cascades live user data |
| `POST /api/predict` | Session + CSRF + origin; 14-field contract; PII/extra fields rejected |
| `POST /api/predict/batch` | Same protection; max 50 applications; all-or-nothing DB commit |
| `GET /api/predictions` | Only caller-owned history; no raw feature values or user IDs |
| `DELETE /api/predictions/{reference}` | Ownership check; deletes one caller-owned assessment |
| `POST /api/predictions/{reference}/outcome` | Ownership check; unverified Good/Bad feedback |
| `POST /api/predictions/{reference}/explain` | Ownership + consent; optional HF integration |
| `GET /api/monitoring` | Caller-only count, drift, and feedback performance |
| `GET /api/model`, `/api/report` | Session; aggregate findings only |
| `GET /health` | Public minimal `status: ok`; no infrastructure/model details |

API clients must send the configured `Origin`, obtain the session cookie from signup/login, and use the returned `csrf_token` as `X-CSRF-Token` for mutations. Public prediction references are intentionally returned for feedback/deletion; internal account IDs are not returned. No privileged role or admin API exists, so clients cannot request an elevated role. Password reset is not implemented; there is no weak reset/OTP endpoint to exploit.

## Hugging Face integration

Local scikit-learn scoring works without an API key. To optionally explain an assessment, set `HF_ENABLED=true`, `HF_TOKEN` and `HF_MODEL` server-side. Choose a chat model available to your Hugging Face account/provider. Restart the service. Startup fails when the integration is enabled without either variable.

Clicking the explanation button gives explicit consent. The server sends only a coarse band plus three feature names. It sends no application values, email, reference, financial amounts, birth date, or bank information. Authentication headers necessarily carry the operator's HF token to HF; provider/egress metadata is subject to the provider's policies. Provider timeouts return a generic 503 and do not affect risk prediction. Output is rendered as text. The live call was not tested because no token was supplied; the exact request shape and minimization were tested with a stub. Free-tier availability, model support, quotas, and hosting costs are not guaranteed.

## Monitoring and data retention

Every prediction stores account linkage, validated input fields, risk score, model version, reasons, and timestamp. Feedback is unverified and never automatically becomes training data. At 20 account-owned records, monitoring computes PSI against train-only numeric bins; an illustrative PSI >0.2 raises a drift alert. At 20 labels with both classes, it computes account-only AUC/Brier. Monitoring has no global cross-account data access. Labels must have a fixed observation horizon, provenance, and maturity before any future training.

Production Compose runs daily retention: live predictions expire after 90 days, sessions after one hour, and expired rate-limit pseudonyms are purged. In local demos run `python -m scripts.retention` periodically with environment variables loaded. Emails and password hashes remain until account deletion. Database/volume backups and encryption are operator responsibilities: use encrypted volumes, a documented maximum 30-day backup retention, and deletion tombstones/reapplication after restores. Do not restore deleted accounts accidentally. Immediate backup erasure is not implemented.

## Testing and audit

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --check frontend/app.js
python scripts/security_scan.py
```

Tests exercise live FastAPI routes through TestClient, Argon2 hashing, ownership checks, sessions, rate limits, CSRF/CORS, SQL/text injection, payload/batch bounds, response minimization, account cascading deletion, provider minimization, model integrity, and production configuration guards. Set `TEST_DATABASE_URL` in the environment to a **disposable** PostgreSQL database to run the same tests against PostgreSQL; tests intentionally drop project tables there. No real account credentials are embedded in tests.

The delivered version passed 43 tests and a real-loopback HTTP smoke test. Report regeneration with `--no-pdf` needs no PDF dependencies. For PDF output, install `requirements-dev.txt`; the generator also expects DejaVu fonts (install fonts-dejavu-core on Linux), then run `python scripts/build_report.py`.

See `reports/security_privacy_audit.md` for every requested check, the complete data map, secret-variable inventory, attack paths, fixes, and deployment blockers. The automated scanner reports file/line/type only, never matched values. It is a heuristic supplement, not proof of zero vulnerabilities. Dependency vulnerability/CVE scanning and browser E2E/accessibility QA are still required on the target deployment environment.

**Git history warning: rotate any previously hardcoded secrets immediately.** Removing a secret from the current file does not remove it from Git history, artifacts, caches, or released images. This was a new project with no supplied prior repository/history and no discovered real secrets in source; earlier private history could not be inspected.

## Production deployment

The current deliverable is not publicly deployed. Native Sites hosting runs Workers and does not run this Python/PostgreSQL server. No fake cloud frontend has been published. Use your own Docker-capable host or managed Python service and managed PostgreSQL.

1. Generate an environment file privately, then set `APP_ENV=production`, `DOMAIN` to your real domain and `APP_ORIGIN` to its exact HTTPS origin. Provision DNS/TLS before accepting users.
2. Set `DATABASE_URL` to the non-superuser application role on PostgreSQL, using **sslmode=verify-full** and **sslrootcert=/app/certs/ca.crt**. Server cert SAN must include the DB hostname (`db` for this Compose setup). Keep credentials only in your secret manager/environment file.
3. Supply `certs/ca.crt`, `certs/server.crt`, and `certs/server.key`; keep them excluded from Git/build archives. Server private key must be readable only by the postgres container user, with the ownership and permissions required by PostgreSQL. Managed PostgreSQL can replace the bundled DB service; use its trusted CA.
4. Run `docker compose -f compose.production.yaml up --build -d`. Only Caddy publishes ports 80/443. App and DB ports stay private. Caddy forwards to the internal app; Uvicorn trusts forwarded headers only from the fixed edge IP 172.28.0.10. Caddy ignores untrusted inbound forwarded IP values. If your host already uses this subnet, adjust the private network and trusted proxy IP together.
5. Verify startup, HTTPS, hostname-verified PostgreSQL TLS, database grants, frontend workflows, login rate limits from distinct real client IPs, dependency scanning, backups, deletion/retention, and the tests against PostgreSQL. Do not treat the local SQLite test pass as proof of deployed infrastructure security.

Model policy stays `human_review_only` in production. A real lending release requires current representative data, a defined matured outcome, documented affordability/business policy, demographic fairness review, source-owner relationship confirmation, and prospective evaluation. No profitability estimate is justified without loss, recovery, funding cost, revenue, and exposure-at-default data.

## Report and presentation

`reports/project_report.md`, `project_report.html`, and the PDF explain the full pipeline and final findings. Every chart is a PNG image in `reports/figures/`. `reports/presentation_outline.md`.

## Documentation references

- https://scikit-learn.org/stable/common_pitfalls.html
- https://scikit-learn.org/stable/modules/calibration.html
- https://fastapi.tiangolo.com/advanced/events/
- https://huggingface.co/docs/huggingface_hub/package_reference/inference_client
- https://www.postgresql.org/docs/current/libpq-ssl.html
- https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
