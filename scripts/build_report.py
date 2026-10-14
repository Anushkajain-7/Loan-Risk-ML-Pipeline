"""Generate a source-backed Markdown/HTML/PDF report from verified artifacts."""
import json,html,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def build(no_pdf=False):
    m=json.loads((ROOT/'artifacts/metadata.json').read_text());q=m['quality'];t=m['test'];e=json.loads((ROOT/'reports/eda.json').read_text())
    blocks=[]
    def heading(s):blocks.append(('h',s))
    def para(s):blocks.append(('p',s))
    def table(headers,rows):blocks.append(('t',(headers,rows)))
    def image(name,caption):blocks.append(('i',(name,caption)))
    heading('LoanLens | End-to-end loan-risk project')
    para('Prepared for Anushka Jain | 14 October 2026 | Research application and reproducible findings')
    para('Decision: the supplied data supports a limited historical risk-ranking experiment, not a validated policy for issuing loans to current applicants. The application always requires human review. It never automatically approves or declines a loan.')
    para(f"The selected {m['winner']} model scores ROC-AUC {t['roc_auc']:.3f} on {t['n']} later first loans. At the illustrative threshold {m['threshold']:.2f}, it identifies all 65 bad loans but also flags 62 of 64 good loans. This operational tradeoff is unsuitable for automated decisions. Infrastructure deployment remains unverified.")
    heading('1. Problem definition and decision policy')
    para('The target is Bad=1 and Good=0, using the supplied flgGood label. The desired output is a risk probability for an application available at origination. No bad-loan definition, performance measurement date, observation horizon, interest/revenue, loss severity, recoveries, or business cost table was supplied. Therefore the model cannot establish expected profit or loss, set a justified approval cutoff, or identify all future applicants who should receive a loan.')
    para('Success is evaluated with ROC-AUC, average precision, precision/recall/F1 for Bad, Brier score, calibration, and the confusion matrix against a constant-prior baseline. Accuracy alone would conceal the threshold tradeoff. All assessments are advisory and must undergo policy, affordability, and human review outside the model.')
    heading('2. Dataset inspection and relationship validation')
    table(['Inspection','Observed result'],[
      ['Application Data',f"{q['application_rows']} rows; 31 original fields"],['Loan Performance',f"{q['performance_rows']} rows; 2 fields; {q['performance_customers']} customer prefixes"],
      ['Dates',q['date_min']+' to '+q['date_max']],['Mixed identifier types',f"{q['numeric_application_ids']} application IDs stored as integers"],
      ['Matched first loans',f"{q['matched_first_loans']} = {q['good']} Good + {q['bad']} Bad"],
      ['Excluded applications',f"{q['malformed_application_ids']} malformed IDs; {q['unmatched_valid_applications']} valid unmatched IDs"],
      ['Repeat outcomes',f"{q['repeat_loan_rows']} suffix -02 rows; {q['conflicting_repeat_customer_labels']} customers have differing labels"],
      ['Unmatched first outcomes',str(q['unmatched_first_loan_outcomes'])]])
    para('Normalize plausible customer IDs to lowercase strings and pad to 10 characters only after type conversion. Match customer_id to the prefix of idLoan, then select suffix -01. This yields a one-to-one merge validated explicitly. A naive case-sensitive join fails; a string-only join also drops integer IDs. Invalid or unmatched IDs are quarantined through counts, not silently assigned labels. Duplicate primary IDs or unexpected outcome labels cause ingestion to fail.')
    para('Crucial assumption: the prefix really denotes the same customer and -01 denotes the first loan. This is consistent with the data structure but cannot be proven without a source dictionary or owner confirmation. Repeated-loan labels are not attached to the first application. Application dates span roughly six months across seven calendar months, with partial endpoint months.')
    image('01_labels.png','641 matched first-loan outcomes. This matched cohort differs from the full loan table and is the modeling population.')
    heading('3. Data quality and EDA')
    para('All application status values are Approved. Missing values include payment_amount_approved (20), other_phone_type (285), how_use_money (2), and bank_account_duration (1). Most of these fields are excluded; retained missingness is handled within the fitted pipeline. Two matched borrowers report rent greater than income. Ages at origination range from about 18 to 80; date of birth is excluded from modeling and used only for the offline aggregate audit.')
    para('Score minima include L2C=50 and several FICO-family scores=222. Their meaning is unknown: special/sentinel codes versus valid low scores must be clarified before changing them to missing values. Numeric amount, income, rent, and score columns are bounded and checked for non-finite values at runtime. Inputs outside train-only ranges receive an explicit warning and human-review gate.')
    table(['Retained numeric input','Minimum','Median','Maximum'],[[c,str(v['min']),str(v['median']),str(v['max'])] for c,v in e['ranges'].items()])
    para('Currency, duration units, rent/own boolean semantics, and score-provider definitions were not supplied. The UI uses dataset units and excludes the ambiguous rent/own flag. No assumption is made that these historical, US-style credit fields are valid for Indian lending or INR amounts.')
    heading('4. Processing, feature engineering and experiments')
    para('The 14 raw features are requested amount/duration; monthly income/rent; five raw scores; direct-deposit and ACH indicators; coarse residence/bank-account tenure; and payment frequency. Two derived features measure requested amount/income and rent/income. Excluded fields include customer ID, email, birth date, ZIP, bank routing, approval status/amount/duration/payment fields, payment amounts and counts with uncertain timing, email tenure, phone categories, and use-of-money text.')
    para('Numeric preprocessing uses median imputation, missingness indicators, and StandardScaler. Categories use most-frequent imputation and one-hot encoding with unknown categories ignored. Transformations are inside sklearn Pipeline/ColumnTransformer and are learned only from training folds. Scaling benefits logistic regression; tree models do not require it. No oversampling is used because matched outcomes are approximately 55% Bad rather than severely imbalanced.')
    table(['Partition','Rows','Use'],[[k,str(v),{'train':'Candidate fitting + expanding-window CV','calibration':'Sigmoid calibration of frozen winner','threshold_validation':'Illustrative cost threshold selection','test':'Untouched chronological evaluation'}[k]] for k,v in m['split'].items()])
    table(['Candidate','Mean CV average precision','Mean CV ROC-AUC'],[[r['name'],f"{r['cv_ap']:.3f}",f"{r['cv_auc']:.3f}"] for r in m['experiments']])
    para('Three expanding-window CV folds compare dummy baseline, regularized logistic regression, shallow random forest, and histogram gradient boosting. The forest wins on mean CV average precision. Calibration and threshold selection use separate 64-row validation subsets; both are small. Seeds are fixed to 42. JSONL tracks parameters/fold metrics; metadata captures source hash, split dates, versions, and exclusion reasons.')
    para('The threshold minimizes 5 x missed Bad + 1 x flagged Good on threshold-validation only. The 5:1 cost is illustrative and was not supplied by the lender. Test labels are not used to select a candidate, calibrator, or cutoff. Chronological splitting reduces random-split optimism, but missing label observation dates prevent verification that all earlier labels had matured before later applications.')
    heading('5. Final holdout findings')
    table(['Metric','Selected model','Constant-prior baseline'],[[name,f"{t[key]:.3f}",f"{m['baseline'][key]:.3f}"] for name,key in [('ROC-AUC','roc_auc'),('Average precision','average_precision'),('Brier (lower is better)','brier'),('Bad precision','precision_bad'),('Bad recall','recall_bad'),('Bad F1','f1_bad')]])
    table(['Actual / predicted','Not flagged','Flagged'],[['Good','2','62'],['Bad','0','65']])
    para(f"The holdout contains 65 Bad and 64 Good loans. The selected operating point flags 127 of 129 loans. Specificity is 2/64 = 3.1%. Bootstrap ROC-AUC 95% interval is {t['auc_bootstrap_95'][0]:.3f}-{t['auc_bootstrap_95'][1]:.3f}. This resampling interval is conditional on the observed sample and fixed model; it does not capture dataset-selection, temporal, model-selection, or target-definition uncertainty.")
    image('02_roc.png','ROC-AUC reflects ranking. The modest discrimination and broad uncertainty do not validate an approval policy.')
    image('03_precision_recall.png','Average precision is evaluated against holdout Bad prevalence (0.504). High recall at the selected threshold comes with many false alarms.')
    heading('6. Calibration and explainability')
    para('Sigmoid calibration is fitted on the frozen forest using its own validation subset. The test calibration curve uses five quantile bins, approximately 26 observations each. With this small sample, probability reliability is uncertain. Brier improves over the prior baseline but does not establish production calibration.')
    image('04_calibration.png','Quantile-bin calibration on the chronological holdout; do not interpret a few bins as evidence of dependable individual probabilities.')
    para('Global permutation importance measures change in holdout AUC after shuffling a feature; correlated predictors can share or obscure importance. Error bars show variability over 10 shuffles, not confidence in a causal effect. Small importances are unstable. Runtime reference comparisons replace one numeric input with its training median and recompute risk. They are transparent model sensitivities, not causal effects, SHAP values, or formal adverse-action reasons.')
    image('05_importance.png','Global predictive importance, computed after model/threshold selection; it does not affect selection and is not a causal explanation.')
    heading('7. Responsible AI and limitations')
    para('Removing direct identifiers and age from training does not guarantee fairness: scores, tenure, income, and payment methods may act as proxies. Only a limited offline age-band comparison is possible. No sex, race, disability, reliable region, or other relevant demographic audit dataset was supplied. Assess legal/policy applicability with a qualified domain owner before a lending release.')
    table(['Age at origination','Holdout rows','ROC-AUC','Bad recall'],[[r['age_band'],str(r.get('n','suppressed')),f"{r['auc']:.3f}" if 'auc' in r else 'not estimated',f"{r['recall_bad']:.3f}" if 'recall_bad' in r else 'not estimated'] for r in e['age_subgroup_audit']])
    para('The age25-39 group has AUC0.439 (44 records) versus0.696 for age40+ (76 records); under25 is suppressed because there are fewer than20 observations. These unstable descriptive differences deserve investigation and cannot certify fairness or establish discriminatory causation. Recall equality at the almost-all-flagged cutoff is not evidence of fair treatment.')
    para('Major limitations: very small data; only historically approved borrowers; unmatched outcome coverage; source-relationship ambiguity; repeat-loan ambiguity; obsolete 2010-2011 population; undefined Bad/horizon; incomplete point-in-time feature/label provenance; unknown score sentinels; unknown currency/units; narrow amount range; uncertain calibration; cost-sensitive threshold dominated by false positives; no prospective evaluation or population fairness validation.')
    para('Additional useful data: contemporary application and origination IDs; decisions/declines with legally/ethically observable outcomes; matured delinquency definitions and observation dates; source field timestamps; verified income/employment and existing debt/obligations; affordability; bureau history/sentinel dictionary; interest/fees, loan exposure, realized losses, recovery and funding costs; acquisition channels; demographic audit fields governed separately from prediction features; macroeconomic context; consent/retention metadata.')
    heading('8. Connected application and future requests')
    para('FastAPI serves the frontend and JSON APIs from one origin. Create a private account, fill the 14-field form or load synthetic values, assess, view probability/range warnings/reference comparisons, record outcomes, monitor, and delete an assessment/account. Batch JSON supports up to50 applications with a64KiB body cap. The backend runs the packaged model; no client-side risk formula or fabricated API result is used.')
    para('The model loads once in lifespan. A SHA-256/runtime check precedes loading; only trusted operator-controlled joblib files are permitted. JSON registry/version snapshots preserve research releases. Future requests always use the frozen deployed version; no background training alters a live model. Retraining is an offline controlled release, requiring renewed evaluation and report review.')
    para('Account-only monitoring computes PSI on train-derived numeric bins after20 predictions, with an illustrative0.2 alert. After20 labeled predictions and both classes, it reports AUC/Brier. Feedback is user-reported/unverified and never automatically enters training. Monitoring therefore detects signals, not definitive population drift or validated realized lending performance.')
    para('Optional Hugging Face chat explanation is server-side, disabled by default, and consent-based. It receives only a coarse risk band and feature names. Scoring requires no external AI service. HF free-tier availability/quotas and model support are account-dependent. No live HF token was provided; provider request minimization and failure behavior were tested with stubs.')
    heading('9. Security, privacy and testing')
    para('Passwords are Argon2id-hashed; opaque session cookies are HttpOnly/SameSite=Strict and Secure in production. Origin/CSRF checks protect writes; database-backed atomic limits protect login/signup/model calls. No admin role, default accounts, uploads, password reset, analytics, browser storage, public Swagger, arbitrary file server, or third-party payment service exists. SQLAlchemy binds query parameters; DOM renders output with textContent. Live account deletion cascades sessions/assessments/outcomes.')
    table(['Collected data','Stored / external destination'],[['Account email','Application DB; not sent externally'],['Password','Salted Argon2id hash only in DB'],['Financial input/score/tenure fields','Caller-owned prediction JSON; no AI prompt export'],['Session / CSRF','Keyed token digest and session expiry; protected cookie/in-memory CSRF'],['IP','Transient; only HMAC rate-limit pseudonym persisted'],['Optional explanation','HF receives band + feature names + service authentication/network metadata']])
    para('No real source secrets were found. DATABASE_URL, AUTH_SECRET, DB bootstrap/app passwords, and optional HF_TOKEN are environment-only. .env/certificates/raw borrower files are excluded from source/build archives; a blank .env.example documents configuration. No inherited Git history was supplied. Rotate any previously hardcoded secrets immediately, because old history/images/caches retain them.')
    para('The complete per-check audit and attack/data-flow maps are in security_privacy_audit.md. Application responses have generic errors/correlation IDs, no-store, nosniff, DENY, one-year HSTS, and self-only-script CSP. Production startup rejects missing critical settings, SQLite, plaintext/unverified PostgreSQL TLS, and non-HTTPS/wildcard origins.')
    para('Validation: 43 tests passed against the live FastAPI TestClient with a disposable SQLite adapter. Tests include ownership, anonymous APIs, expired/tampered sessions, Argon2, Secure-cookie configuration, CSRF/CORS, role injection, SQL/script-shaped input, rate boundaries, payload/batch limits, data deletion, error/log redaction, monitoring, provider minimization/timeouts, and model contract/integrity. JavaScript syntax was checked. HTTP smoke-test and secret-scan evidence are bundled when available.')
    heading('10. Deployment and release gates')
    para('Delivered: Dockerfile, development PostgreSQL Compose, production Compose with Caddy HTTPS/private DB and verified PostgreSQL TLS, separate non-superuser DB app role, environment generator, local SQLite launcher, and daily retention worker. App/db ports are private in production; only the edge publishes80/443. The fixed trusted proxy address prevents indiscriminate X-Forwarded-For trust. Production requires operator-supplied domain, certificates, environment values, encrypted storage, and backup policy.')
    para('Not verified here: Docker build/runtime, actual PostgreSQL queries/cascades/TLS/grants, public HTTPS/proxy behavior, live Hugging Face, dependency CVEs, browser E2E/accessibility, concurrency/load, encrypted backups, and restore/deletion handling. There is no public deployment URL. Worker-only native hosting cannot run this Python/PostgreSQL application. The package is runnable locally and deployable to a suitable host after these checks, not certified production-ready.')
    para('Live predictions expire after90 days under the supplied production retention worker; sessions expire afterone hour; rate pseudonyms expire by their window. Account data remains until deletion. Backups require encrypted storage, a maximum30-day policy, and tombstone/reapplication controls after restores. Immediate third-party/provider or backup deletion is not implemented. Infrastructure privacy settings are operator responsibilities.')
    para('Next evidence-driven step: confirm source semantics and obtain current, representative, matured lending data; define costs/affordability and human policy; validate subgroup performance and probability calibration prospectively. Only then consider an independently governed loan-decision policy. This project presents its weak findings honestly and keeps an unconditional human-review gate.')
    heading('References and reproducibility')
    for ref in ['Source: supplied AssessmentDataScientist(2).xlsx; Application Data + Loan Performance sheets. Raw workbook and borrower identities are not included in the release archive.',
      'Source SHA-256: '+q['source_sha256'], 'Model version: '+m['version']+'; SHA-256: '+m['sha256'],
      'scikit-learn: https://scikit-learn.org/stable/common_pitfalls.html',
      'Calibration: https://scikit-learn.org/stable/modules/calibration.html',
      'FastAPI lifespan: https://fastapi.tiangolo.com/advanced/events/',
      'HF client: https://huggingface.co/docs/huggingface_hub/package_reference/inference_client',
      'PostgreSQL TLS: https://www.postgresql.org/docs/current/libpq-ssl.html',
      'Caddy proxy: https://caddyserver.com/docs/caddyfile/directives/reverse_proxy']:
        para(ref)
    import re
    # Keep numerical references legible in prose without changing hashes/paths/tables.
    blocks=[(kind,re.sub(r'(?<=[A-Za-z])(?=\d)', ' ', re.sub(r'(?<=\d)(?=[A-Za-z])',' ',value)).replace('afterone','after one').replace('Argon 2 id','Argon2id').replace('L 2 C','L2C')) if kind=='p' and not value.startswith(('Source SHA','Model version','scikit-learn:','Calibration:','FastAPI lifespan:','HF client:','PostgreSQL TLS:','Caddy proxy:')) else (kind,value) for kind,value in blocks]
    md=[];web=['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LoanLens project report</title><link rel="stylesheet" href="report.css"></head><body><main>']
    for kind,value in blocks:
        if kind=='h':md.append('\n## '+value+'\n');web.append('<h2>'+html.escape(value)+'</h2>')
        elif kind=='p':md.append(value+'\n');web.append('<p>'+html.escape(value)+'</p>')
        elif kind=='i':name,caption=value;md.append(f'![{caption}](figures/{name})\n');web.append(f'<figure><img src="figures/{name}" alt="{html.escape(caption)}"><figcaption>{html.escape(caption)}</figcaption></figure>')
        else:
            headers,rows=value;md.append('| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+'\n'.join('| '+' | '.join(row)+' |' for row in rows)+'\n')
            web.append('<table><thead><tr>'+''.join('<th>'+html.escape(s)+'</th>' for s in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(s)+'</td>' for s in row)+'</tr>' for row in rows)+'</tbody></table>')
    web.append('</main></body></html>')
    report=ROOT/'reports';(report/'project_report.md').write_text('\n'.join(md));(report/'project_report.html').write_text('\n'.join(web))
    (report/'report.css').write_text('body{background:#eef2f4;color:#172c39;font:16px/1.65 system-ui,sans-serif;margin:0}main{max-width:950px;margin:auto;background:white;padding:50px}h2{color:#19645c;margin-top:45px;line-height:1.25}table{width:100%;border-collapse:collapse;font-size:13px;margin:25px 0}th,td{text-align:left;border-bottom:1px solid #dce5e7;padding:12px;vertical-align:top}th{background:#edf5f3}img{width:100%}figure{margin:30px 0}figcaption{font-size:13px;color:#566b75}p{overflow-wrap:anywhere}@media(max-width:650px){main{padding:22px}table{font-size:11px}th,td{padding:5px}}')
    if no_pdf:return
    from reportlab.pdfgen import canvas
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Image,KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase import pdfmetrics
    fonts=Path('/usr/share/fonts/truetype/dejavu')
    pdfmetrics.registerFont(TTFont('DejaVu',str(fonts/'DejaVuSans.ttf')));pdfmetrics.registerFont(TTFont('DejaVuBold',str(fonts/'DejaVuSans-Bold.ttf')))
    styles=getSampleStyleSheet();styles.add(ParagraphStyle(name='BodyR',fontName='DejaVu',fontSize=9,leading=14,spaceAfter=10,textColor=colors.HexColor('#263b46')))
    styles.add(ParagraphStyle(name='HeadR',fontName='DejaVuBold',fontSize=16,leading=21,spaceBefore=18,spaceAfter=12,textColor=colors.HexColor('#17665c'),keepWithNext=True))
    styles.add(ParagraphStyle(name='CellR',fontName='DejaVu',fontSize=7.5,leading=11,wordWrap='CJK'))
    styles.add(ParagraphStyle(name='CapR',fontName='DejaVu',fontSize=8,leading=12,spaceAfter=15,textColor=colors.HexColor('#576d77')))
    story=[]
    for kind,value in blocks:
        if kind in {'h','p'}:story.append(Paragraph(html.escape(value),styles['HeadR' if kind=='h' else 'BodyR']))
        elif kind=='i':
            name,caption=value;story.append(KeepTogether([Image(str(report/'figures'/name),width=460,height=259),Paragraph(html.escape(caption),styles['CapR'])]))
        else:
            headers,rows=value;data=[[Paragraph(html.escape(c),styles['CellR']) for c in row] for row in [headers]+rows]
            widths=[460/len(headers)]*len(headers)
            if len(headers)==2:widths=[160,300]
            tb=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT');tb.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e7f1ef')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8),('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#cfdddf'))]));story.extend([tb,Spacer(1,14)])
    def footer(c,doc):
        c.setFont('DejaVu',7);c.setFillColor(colors.HexColor('#607a85'));c.drawString(50,30,'LOANLENS / Research findings / 14 October 2026');c.drawRightString(545,30,str(doc.page))
    SimpleDocTemplate(str(report/'LoanLens_Project_Report.pdf'),pagesize=(595,842),leftMargin=50,rightMargin=50,topMargin=45,bottomMargin=50).build(story,onFirstPage=footer,onLaterPages=footer)
    print('Generated Markdown, HTML, CSS and PDF project reports.')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--no-pdf',action='store_true');build(p.parse_args().no_pdf)
