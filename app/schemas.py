from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
import re
class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
class Credentials(Strict):
    email:str=Field(min_length=3,max_length=254)
    password:str=Field(min_length=12,max_length=128)
    @field_validator('email')
    @classmethod
    def email_valid(cls,v):
        v=v.strip().lower()
        if not re.fullmatch(r'[a-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+',v):raise ValueError('Invalid email')
        return v
class Confirm(Strict):password:str=Field(min_length=1,max_length=128)
class Application(Strict):
    amount_requested:float=Field(ge=1,le=1000000)
    loan_duration:int=Field(ge=1,le=120)
    monthly_rent_amount:float=Field(ge=0,le=1000000)
    monthly_income_amount:float=Field(gt=0,le=10000000)
    raw_l2c_score:float=Field(ge=0,le=1000)
    raw_FICO_telecom:float=Field(ge=0,le=1000)
    raw_FICO_retail:float=Field(ge=0,le=1000)
    raw_FICO_bank_card:float=Field(ge=0,le=1000)
    raw_FICO_money:float=Field(ge=0,le=1000)
    bank_account_direct_deposit:bool
    payment_ach:bool
    residence_duration:Literal['3+ years','1-2 years','7-12 months','6 months or less']
    bank_account_duration:Literal['3+ years','1-2 years','7-12 months','6 months or less']
    payment_frequency:Literal['Bi-weekly','Monthly','Semi-monthly','Weekly']
class Batch(Strict):applications:list[Application]=Field(min_length=1,max_length=50)
class Feedback(Strict):outcome:Literal['Good','Bad']
class ExplainRequest(Strict):consent:bool
class PredictionOut(Strict):
    reference:str
    bad_probability:float
    risk_band:str
    recommendation:str
    model_version:str
    warnings:list[str]
    factors:list[dict]
