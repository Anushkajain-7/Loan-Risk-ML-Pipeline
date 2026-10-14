# LoanLens security, privacy and release audit

Audit date: 14 October 2026. Scope: all authored source, configuration, frontend files, model metadata, build/deployment definitions, generated report content, and API tests. There was no existing app or Git repository to repair. Controls were implemented in the new project; no inherited production service was inspected.

**Release result: code checks pass; public deployment is blocked pending infrastructure verification.** Tests use the real FastAPI application and a disposable SQLite adapter. Docker, PostgreSQL runtime, public TLS, live Hugging Face, browser automation, and dependency vulnerability scanning were not available/verified. This is not a claim of independent penetration testing or production certification.

Final evidence: **43 tests passed**, JavaScript syntax passed, both Compose YAML files parsed, and a real-loopback Uvicorn HTTP smoke test passed signup/session/CSRF, model prediction, history, report/styles/chart routes, and account deletion. A single synthetic prediction took 0.163 seconds locally; this is not a load or latency guarantee. The final heuristic scan covered 47 authored text/configuration/evidence files with zero findings. Evidence files: test-results.xml, http_smoke_test.json, secret_scan.json. Authenticated chart assets are requested only after sign-in to avoid cached unauthorized image failures.

## Secret inventory and safety pass

No real API key, password, token, credential-bearing URI, or private key was found in the authored source/configuration. No old secret value was moved, since this project started in an empty workspace. All credential-bearing settings were implemented through environment variables from the start. The heuristic scanner records only location/type; it never prints matched values. Model hashes are integrity identifiers, not secrets. Synthetic input values and documentation placeholders are not credentials. Tests generate account passwords and session/signing values at runtime.

| Setting | Where needed | Source/access | Result |
| --- | --- | --- | --- |
| DATABASE_URL | app/config.py, app/db.py | Server environment; may contain DB username/password | Required; no credential URI literal |
| AUTH_SECRET | app/config.py, app/main.py | Server environment; keyed session/IP digests | Required; generated randomly; never browser-exposed |
| POSTGRES_USER / POSTGRES_PASSWORD | Compose DB bootstrap | Environment file/secret manager | Independent bootstrap credentials; no defaults |
| APP_DB_USER / APP_DB_PASSWORD | scripts/init_db.sh; runtime DATABASE_URL | Server environment | Separate non-superuser role; not in process arguments |
| HF_TOKEN | app/config.py; app/main.py explain | Server environment | Required only when optional HF_ENABLED=true |
| HF_MODEL / HF_ENABLED | Optional explanation configuration | Server environment | Public-safe model identifier/feature flag; not secrets |
| APP_ORIGIN / APP_ENV / DOMAIN | Origin and deployment policy | Environment | Public-safe configuration; exact production HTTPS origin |
| ARTIFACT_DIR | Model load path | Environment or project-local fallback | Non-secret; no arbitrary client path accepted |
| PostgreSQL private key | production DB TLS | Ignored operator-supplied certs/server.key mount | Never in source, image, archive, or browser |
| Session cookie | Login/signup response | Cryptographically random; HttpOnly cookie | Only HMAC digest persisted; not a source secret |
| CSRF token | Login/me response and in-memory JS | Random, session-bound | Required for all authenticated writes; no browser storage |

| Requested secret check | Status | Evidence/fix |
| --- | --- | --- |
| All secrets in environment | PASS | Config only reads secret env vars; generator writes ignored .env with mode 0600 |
| Supabase anon + RLS / service role | NOT APPLICABLE | No Supabase SDK, key, table, or client integration |
| Stripe public vs secret | NOT APPLICABLE | No Stripe/payment integration |
| DB connection strings | PASS | DATABASE_URL required; no credential-bearing URI in source |
| OAuth/JWT secret separation | PASS / NOT APPLICABLE | No OAuth/JWT; opaque server-validated sessions keyed by server-only AUTH_SECRET |
| OpenAI/SendGrid/Twilio/Firebase/AWS keys | NOT APPLICABLE | No integration with these services |
| NEXT_PUBLIC_/REACT_APP_ secret exposure | PASS | Neither framework/env prefix used; no runtime secrets served by frontend |
| .gitignore and .env.example | PASS | .env/.env.* ignored, exception only for blank .env.example; certs and DBs ignored |
| Logs and error responses | PASS in authored code | Access logs off; rejection inputs omitted; provider exceptions suppressed; logs include correlation ID + exception class only |
| Historical Git secrets | NOT VERIFIED | No prior Git history supplied; README explicitly requires immediate rotation of any previously hardcoded secrets |

## Complete personal-data flow map

| Collection point | What enters | Travel/processing | Live storage | External destinations | Removal/retention |
| --- | --- | --- | --- | --- | --- |
| Offline workbook ingestion | Customer IDs, email, date of birth, ZIP, bank routing number; financial fields; timestamps; outcome labels | Local Python RAM; normalize IDs only for matching; exclude identifiers/protected/approval fields before modeling | Source workbook stays under the owner's control in ignored data/raw; trained artifact contains learned parameters/partitions and aggregates | None; never sent to HF or copied into app database | Raw source retention is owner's policy; archive omits raw workbook; models may retain statistical/memorization risk and must be access-controlled |
| Signup/login form | Account email, password | Same-origin HTTPS JSON -> validation -> parameterized DB lookup -> Argon2id hash/verify | Email + salted Argon2id password hash in users; password never stored | None in authored app | Account deletion cascades live account rows; no reset/OTP service exists |
| Login/signup result | Session cookie + CSRF token | Server generates random token; cookie travels through browser cookie jar; CSRF held in JS memory | HMAC token digest, user linkage, expiry, CSRF in sessions | No third-party SDK | One-hour expiry; logout current session; deletion all sessions; scheduled cleanup |
| Assess form / batch JSON | Amount, duration, income, rent, five scores, ACH/direct-deposit booleans, coarse tenure, payment frequency | Strict 14-field validation -> ratios -> saved preprocessing pipeline -> calibrated model -> safe response | Caller-owned input JSON, score, version, factors, timestamp, public reference | None during normal scoring | Assessment delete or account delete immediately removes live rows; daily 90-day expiry in production |
| Outcome buttons | Public prediction reference + Good/Bad label | Ownership check -> same account's prediction row | Outcome integer in predictions; unverified provenance documented | None | Deleted with assessment/account; 90-day prediction retention |
| Optional explain button | Consent + reference | Ownership check -> load coarse band/feature names; operator token authenticates API | Explanation not persisted in database; text displayed in current DOM | HF/provider sees band, 3 feature names, model ID, service auth token, egress/network metadata; no email, applicant values, raw scores, bank data, or reference in prompt | Provider retention is governed by its policy/account settings; no external deletion API implemented; integration off by default |
| HTTP requests | IP address via ASGI; normal browser headers, cookies, Origin | Raw IP used transiently for keyed rate-limit hash; trusted proxy is fixed edge IP in production | HMAC network/account bucket key + count + expiry; no raw IP/header dump | Hosting/network operator necessarily receives request metadata; no analytics/error SDK | Expired limit keys purged daily; pseudonyms have no stored account foreign key; no raw IP in app logs |
| History/model/report/monitoring | Auth cookie; account-only selection | Ownership filter; aggregate or curated response fields | No new PII collection | None | Browser DOM cleared on sign-out; no localStorage/sessionStorage/IndexedDB/service-worker cache |
| Account deletion | Password + checkbox in UI | Session/CSRF/origin -> hash verification -> DB cascade | No deletion password persisted | None | Live user, sessions, predictions, feedback removed transactionally; backups require operator expiry/tombstone replay |

No applicant name, phone, address, DOB, card number, payment details, user device fingerprint, browser analytics event, or free-text biography is requested by the deployed app. Unknown fields, including email on a prediction input, are rejected. Account email is distinct from applicant data.

## Requested privacy checks

| Check | Status | Implemented action / remaining limit |
| --- | --- | --- |
| Enumerate collection and destinations | PASS | Complete map above; offline source separated from runtime inputs |
| Clean all logs | PASS in authored code | No frontend console logging; no request-body/PII logging; no exception payload/traceback logging; launcher/Compose disable access logs; infrastructure logs require operator review |
| Third-party data minimization | PASS in request-shape test | Only optional HF call; coarse risk band + feature names; explicit consent; provider unavailable returns generic 503 |
| Hash passwords | PASS | Argon2id with per-password salt, time_cost=3, memory_cost=65536 KiB, parallelism=2; hash never returned |
| Cookie flags | PASS in code/tests | HttpOnly + SameSite=Strict; Secure in production; deliberately non-Secure only for loopback HTTP demo |
| No PII in localStorage | PASS | No browser storage APIs; DOM and JS memory cleared/reset on sign-out |
| Filter API responses | PASS | PredictionOut schema, curated history/me/model dictionaries; no user IDs, hashes, raw input JSON, or cross-account data returned |
| Account/data deletion | PASS on tested DB adapter | Password-confirmed live cascade plus per-assessment deletion; PostgreSQL cascade still needs target-runtime test |
| Backup and disk encryption | OPERATOR REQUIRED | Encrypted volumes/managed DB, max 30-day backup expiry, deletion tombstone handling and restore procedure must be provisioned |

## Deployment readiness checklist

| Requested check | Status | Fix / evidence |
| --- | --- | --- |
| Required environment variables | PASS | DATABASE_URL and AUTH_SECRET fail clearly if absent; production requires PostgreSQL/verified TLS/explicit HTTPS origin; enabled HF requires token/model |
| Debug defaults off | PASS | FastAPI debug=False; no reloader; no test/debug/backdoor/seed endpoint; no default account or literal password |
| Generic client errors | PASS | Validation errors omit inputs; HTTP/unexpected errors expose only generic message + correlation ID; no stack/query/path |
| Correlation in server errors | PASS | UUID created per request; header/error response; server log emits only ID and exception class |
| Security headers on app responses | PASS | nosniff, DENY, one-year HSTS, self-only scripts/CSP, no-store, no-referrer, restrictive Permissions-Policy; tested successes and failures |
| HTTPS and edge error headers | NOT VERIFIED | Caddy production config supplied; no domain/host runtime to exercise HTTPS/proxy failures |
| Login <=5 attempts/min/IP | PASS | Database-backed atomic counter; login 5/min/IP plus 10/hour/email pseudonym; fixed trusted Caddy proxy policy |
| Password reset <=3/hour | NOT APPLICABLE | No password reset/OTP endpoint is implemented |
| Signup and expensive API abuse | PASS in implementation/tests | Signup 3/hour/IP; predict 30/min/account; batch 2/min/account, max50; explain 5/min/account; general authenticated API 120/min/account |
| CORS one frontend origin | PASS | Explicit configured origin; no wildcard; hostile preflight rejected |
| Verified PostgreSQL TLS | PASS configuration guard / NOT VERIFIED runtime | sslmode=verify-full + sslrootcert required; source-side hostname/cert policy; operator must provision valid certs |
| Authenticated private DB | PASS deployment definition / NOT VERIFIED runtime | No published DB port, independently generated credentials, separate app role NOSUPERUSER/NOCREATEDB/NOCREATEROLE; target grants/permissions need verification |
| Docker build and deployment | NOT VERIFIED | Docker unavailable in this environment; configurations are supplied, not claimed built/deployed |
| Browser workflow/responsive QA | NOT VERIFIED | JS syntax and HTTP asset routes checked; no supported browser automation capability available |
| Dependency CVE scan | NOT VERIFIED | Direct dependencies pinned; no CVE service/lockfile security certification claimed |
| Live Hugging Face call | NOT VERIFIED | No real token supplied; disabled default and mocked request-minimization tested |

## Attacker-oriented assessment

These are attack paths evaluated and controls implemented in the new code, not claims that an older app had exploitable vulnerabilities.

| Attack / potential damage | Control or fix | Verification / residual limit |
| --- | --- | --- |
| Change prediction reference to steal/alter/delete another user's financial data | Every reference mutation selects BOTH prediction ID and authenticated owner; history/monitoring filter by owner | Two-account tests reject delete/feedback; active-provider explain rejects unknown/nonowned references; no arbitrary user-ID endpoint |
| Call protected APIs without login | Dependency validates server-persisted opaque session with expiry on every protected route | Parameterized test covers all protected operations; no authentication bypass found |
| Edit/forge/expire auth token | Cookie token is random; server looks up keyed digest, checks expiry; no JWT claims to forge | Tampered and expired session tests pass; logout/delete invalidate sessions |
| Escalate role via signup or JSON/JWT manipulation | No roles/admin routes; Pydantic extra=forbid; role not accepted; no client-controlled privileges | Role in credentials/prediction rejected; /admin and /admin-backdoor return404 |
| Credential stuffing / account creation flood | Atomic persistent login/account/signup buckets; generated passwords, no default accounts | Login boundary and signup bounds tested; distributed attacks/network floods still require edge protection |
| Exhaust model CPU or store infinite uploads | Auth/account limits, bounded batch50, max body64 KiB at app and edge, no upload endpoint; no messaging/referral/promo surface | Body/batch boundaries tested; load/concurrency/host capacity test remains required |
| CSRF to create predictions or delete account | Exact Origin + session-bound CSRF header + Strict cookie; delete also verifies password | Bad/missing Origin and wrong CSRF rejected; malicious site cannot read CSRF via CORS |
| SQL injection in login/filter/reference | SQLAlchemy bound parameters; fixed field names; no raw SQL built from client input | Injection-shaped email cannot authenticate; no client-selected SQL/order/filter |
| XSS via names/text/provider response | No user free-text profile/name fields; numeric/enumerated contract; DOM textContent only; no innerHTML; self-only scripts | Script injection into category rejected; provider text never parsed as HTML; browser CSP still needs live verification |
| Leak .env/.git/admin/docs through file URLs | Fixed allowlists for frontend/chart files; no directory mount; docs/redoc/openapi disabled | Direct exposure/path traversal tests return404; health returns status only |
| Leak secrets/PII in errors | Generic handlers without validation payloads, access logs disabled, provider exception suppressed | Log capture test and response checks; external host log configuration remains outside code audit |
| Replace model with malicious joblib payload | Only trusted build-time artifact paths; SHA/version checked; no model upload API | Integrity test passes; attacker who controls build plus metadata can defeat checksum, so sign images/control release access |
| Plaintext database access or compromised bootstrap role | verify-full production guard; separate least-privilege app role; private DB; operator supplies encrypted storage | Runtime infrastructure not verified; backup/DB operator compromise remains a risk |

## Fixed design risks and unresolved release gates

Fixed: potential cross-account data access, client-secret exposure, plaintext password storage, unbounded input/batch handling, missing session expiry/CSRF, overly detailed validation errors, arbitrary static file access, test/admin endpoints, default credentials, direct applicant export to AI, and production plaintext database fallback were all prevented in the delivered implementation.

No discovered secret was rotated because no real source secret was found. No compromised production account or service was supplied. If prior secrets exist elsewhere, rotate them immediately; source removal is insufficient.

Release gates: provision a Docker-capable host/domain and verified PostgreSQL TLS; run PostgreSQL integration tests and Docker build; perform browser and concurrency testing; scan dependencies; verify encrypted backup/retention/deletion controls and edge headers; decide whether to enable and test HF. The research model remains unsuitable for autonomous lending even after infrastructure gates pass.
