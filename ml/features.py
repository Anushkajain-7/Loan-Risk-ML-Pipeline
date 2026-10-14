"""Shared contract: origination-time inputs only; PII is deliberately absent."""
import numpy as np
import pandas as pd

NUMERIC = ['amount_requested', 'loan_duration', 'monthly_rent_amount', 'monthly_income_amount',
           'raw_l2c_score', 'raw_FICO_telecom', 'raw_FICO_retail', 'raw_FICO_bank_card', 'raw_FICO_money']
CATEGORICAL = ['bank_account_direct_deposit', 'payment_ach', 'residence_duration',
               'bank_account_duration', 'payment_frequency']
DERIVED = ['request_to_income', 'rent_to_income']
FEATURES = NUMERIC + CATEGORICAL
EXCLUDED = ['customer_id', 'email', 'birth_date', 'address_zip', 'bank_routing_number',
            'status', 'amount_approved', 'duration_approved', 'payment_amount_approved',
            'payment_amount', 'num_payments', 'email_duration', 'home_phone_type',
            'other_phone_type', 'how_use_money', 'residence_rent_or_own', 'application_when']

def engineer(frame):
    x = frame[FEATURES].copy()
    for c in NUMERIC:
        x[c] = pd.to_numeric(x[c], errors='coerce').replace([np.inf, -np.inf], np.nan)
    for c in CATEGORICAL:
        x[c] = x[c].map(lambda v: str(v) if pd.notna(v) else np.nan)
    denom = x.monthly_income_amount.replace(0, np.nan)
    x['request_to_income'] = x.amount_requested / denom
    x['rent_to_income'] = x.monthly_rent_amount / denom
    return x
