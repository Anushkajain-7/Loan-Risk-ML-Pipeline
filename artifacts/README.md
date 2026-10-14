# Private model artifacts

Trained models and derived metadata are intentionally excluded from this public repository because they originate from borrower data. Do not upload them or the original workbook to public GitHub.

For authorized local use, either copy the `artifacts/` contents from your private project package into this directory, or train locally using your privately held workbook:

```bash
python -m ml.train --workbook 'data/raw/AssessmentDataScientist(2).xlsx'
python scripts/build_report.py --no-pdf
```

The runtime requires the locally generated `model.joblib` and `metadata.json`. Training also generates the local registry, experiment records, version snapshots, and aggregate EDA output. Keep all model/output files ignored by Git. Only this README is public.
