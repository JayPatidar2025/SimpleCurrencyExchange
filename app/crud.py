from sqlalchemy import func, and_
from sqlalchemy.orm import Session
from .models import ExchangeRate
from datetime import datetime
import uuid

def store_rate(db: Session, base: str, target: str, rate: float):
    new_entry = ExchangeRate(
        id=str(uuid.uuid4()),
        base=base,
        target=target,
        rate=rate,
        timestamp=datetime.utcnow()
    )
    db.add(new_entry)
    db.commit()

def get_latest_rate(db: Session, base: str, target: str):
    return db.query(ExchangeRate).filter_by(base=base, target=target).order_by(ExchangeRate.timestamp.desc()).first()

#def get_all_latest_rates(db: Session):
    # Naive approach: get latest entry for each (base, target)
 #   subquery = (
 #       db.query(ExchangeRate)
 #       .order_by(ExchangeRate.target, ExchangeRate.timestamp.desc())
 #       .distinct(ExchangeRate.target)
 #       .all()
 #   )
 #   return subquery

def get_all_latest_rates(db: Session):
    subquery = (
        db.query(
            ExchangeRate.base,
            ExchangeRate.target,
            func.max(ExchangeRate.timestamp).label("latest_timestamp")
        )
        .group_by(ExchangeRate.base, ExchangeRate.target)
        .subquery()
    )

    latest_rates = db.query(ExchangeRate).join(
        subquery,
        and_(
            ExchangeRate.base == subquery.c.base,
            ExchangeRate.target == subquery.c.target,
            ExchangeRate.timestamp == subquery.c.latest_timestamp
        )
    ).all()

    return latest_rates
