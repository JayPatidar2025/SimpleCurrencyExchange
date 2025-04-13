from sqlalchemy import Column, String, Float, DateTime
from .database import Base
from datetime import datetime

class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    id = Column(String, primary_key=True)
    base = Column(String)
    target = Column(String)
    rate = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

