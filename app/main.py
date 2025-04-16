from fastapi import FastAPI, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from .database import Base, engine, SessionLocal
from . import models, crud, tasks, schemas
from dotenv import load_dotenv
import httpx
import os

# Load environment variables
load_dotenv()

# Create database tables
models.Base.metadata.create_all(bind=engine)

# FastAPI app
app = FastAPI()

# Scheduler
@app.on_event("startup")
def startup():
    tasks.start_scheduler()

# Template & static setup
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Dependency: DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Fetch and store rates from Fixer.io
@app.get("/rates/store")
def fetch_and_store_rates(db: Session = Depends(get_db)):
    key = os.getenv("FIXER_API_KEY")
    url = f"https://data.fixer.io/api/latest?access_key={key}"

    response = httpx.get(url)
    data = response.json()

    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])

    base_currency = data["base"]
    for target_currency, rate in data["rates"].items():
        crud.store_rate(db, base_currency, target_currency, rate)

    return {"message": "Exchange rates stored successfully", "data": data}

# Raw latest rates from Fixer.io (not from DB)
@app.get("/rates")
def get_rates():
    key = os.getenv("FIXER_API_KEY")
    url = f"https://data.fixer.io/api/latest?access_key={key}"
    res = httpx.get(url)
    return res.json()

# API endpoint for exchange via POST
@app.post("/get-exchange", response_model=schemas.ExchangeOutput)
def get_exchange(data: schemas.ExchangeInput, db: Session = Depends(get_db)):
    spread = float(os.getenv("SPREAD_PERCENT", 1.5))
    converted_amount = convert_currency(data.from_currency, data.to_currency, data.amount, db)
    if not converted_amount:
        raise HTTPException(status_code=404, detail="Rate not found in DB")

    fee = (converted_amount * spread / 100)
    total = converted_amount - fee
    
    return schemas.ExchangeOutput(result=total, fee=fee, rate=converted_amount / data.amount)

# Webpage: Home with table and form
@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    rates = crud.get_all_latest_rates(db)
    return templates.TemplateResponse("index.html", {"request": request, "rates": rates})

def convert_currency(from_currency, to_currency, amount, db):
    rate_data_1 = crud.get_latest_rate(db, "EUR", from_currency)
    rate_data_2 = crud.get_latest_rate(db, "EUR", to_currency)

    print(f"Rate EUR → {from_currency}: {rate_data_1}")
    print(f"Rate EUR → {to_currency}: {rate_data_2}")

    if not rate_data_1 or not rate_data_2:
        return None  # One of the rates is missing

    if from_currency == "EUR":
        return amount * rate_data_2.rate
    elif to_currency == "EUR":
        return amount / rate_data_1.rate
    else:
        eur_amount = amount / rate_data_1.rate
        return eur_amount * rate_data_2.rate

import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

@app.post("/exchange", response_class=HTMLResponse)
def calculate_exchange(
    request: Request,
    from_currency: str = Form(...),
    to_currency: str = Form(...),
    amount: float = Form(...),
    db: Session = Depends(get_db)
):
    logger.info(f"Received currency conversion request: {amount} {from_currency} → {to_currency}")

    spread = float(os.getenv("SPREAD_PERCENT", 1.5))

    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    # Get exchange rates for EUR-based conversions
    rate_from_eur = crud.get_latest_rate(db, "EUR", from_currency)
    rate_to_eur = crud.get_latest_rate(db, "EUR", to_currency)

    if from_currency == "EUR":
        rate = rate_to_eur.rate if rate_to_eur else None
    elif to_currency == "EUR":
        rate = 1 / rate_from_eur.rate if rate_from_eur else None
    elif rate_from_eur and rate_to_eur:
        # Convert through EUR if neither currency is EUR
        rate = rate_to_eur.rate / rate_from_eur.rate
    else:
        rate = None  # Missing conversion rates

    # Log rate retrieval
    logger.debug(f"Rate EUR → {from_currency}: {rate_from_eur.rate if rate_from_eur else 'NOT FOUND'}")
    logger.debug(f"Rate EUR → {to_currency}: {rate_to_eur.rate if rate_to_eur else 'NOT FOUND'}")

    if not rate:
        logger.warning(f"Exchange rate not found for: {from_currency} → {to_currency}")
        return templates.TemplateResponse("index.html", {
            "request": request,
            "rates": crud.get_all_latest_rates(db),
            "error": "Rate not found in DB"
        })

    # Apply spread and calculate final amount
    fee = (rate * spread / 100) * amount
    total = amount * rate - fee
    result = schemas.ExchangeOutput(rate=rate, result=total, fee=fee, from_currency=from_currency.upper(), to_currency=to_currency.upper() )

    logger.info(f"Exchange successful: {amount} {from_currency} → {total} {to_currency} @ Rate {rate}, Fee: {fee}")

    return templates.TemplateResponse("index.html", {
        "request": request,
        "rates": crud.get_all_latest_rates(db),
        "result": result,
        "from_currency": from_currency.upper(),
        "to_currency": to_currency.upper()
    })

