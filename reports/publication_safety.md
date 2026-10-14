# Public GitHub publication review

Repository: Anushkajain-7/Loan-Risk-ML-Pipeline. Review date: 14 October 2026.

Included: application/frontend/pipeline source, tests, environment template with blank credential values, deployment definitions, public setup/security documentation, and aggregate findings/chart images/report.

Excluded: real `.env` files, raw/processed borrower data, pretrained model binaries and derived metadata/registry/experiment records, database files/dumps, logs/test evidence, private certificates/keys, caches, credentials, backups, and uploads. Those assets remain private. The repository does not contain the locally generated HF token, database password, or AUTH_SECRET.

Checks performed before upload:

- Source/configuration secret scanner: zero findings; it reports locations/types and does not print values.
- Raw identity comparison: no occurrences of the supplied workbook's 647 borrower email values or 645 well-formed source customer IDs in the selected public text files.
- PDF text comparison: no raw borrower email or customer-ID values.
- Ignore-policy checks: local/nested environment files, dataset files, model binaries/metadata, databases/dumps, private keys, logs, and generated internal evidence are ignored; blank `.env.example` and private-asset README placeholders are eligible for publication.
- Application, frontend, pipeline, scripts, and test source are byte-identical to the previously verified project. Earlier validation passed 43 tests and a real-loopback HTTP smoke test. This publication review does not claim a new runtime test run or production deployment verification.
- The repository was empty before publication; no inherited source/history was present to audit for previously committed secrets. Future accidental secret commits require immediate rotation and historical cleanup as documented in SECURITY.md.

Public reports contain aggregate metrics, field definitions, and source/model integrity fingerprints; they do not contain borrower records. Model hashes are not credentials. Publishing source and security controls is intentional; runtime confidentiality depends on environment isolation, access checks, and secret management rather than hiding application code.

To run from a clone, restore your authorized private artifacts or train locally from the privately held dataset. Git exclusions also apply to newly generated private assets. Gitignore cannot protect assets deliberately force-added or files already tracked in history.
