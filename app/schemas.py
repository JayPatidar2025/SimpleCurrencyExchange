from pydantic import BaseModel

class ExchangeInput(BaseModel):
    from_currency: str
    to_currency: str
    amount: float

class ExchangeOutput(BaseModel):
    result: float
    fee: float
    rate: float

