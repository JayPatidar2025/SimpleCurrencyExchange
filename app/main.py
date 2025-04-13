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
    rate_data = crud.get_latest_rate(db, data.from_currency, data.to_currency)
    if not rate_data:
        raise HTTPException(status_code=404, detail="Rate not found in DB")

    fee = (rate_data.rate * spread / 100) * data.amount
    total = data.amount * rate_data.rate - fee
    return schemas.ExchangeOutput(result=total, fee=fee, rate=rate_data.rate)

# Webpage: Home with table and form
@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    rates = crud.get_all_latest_rates(db)
    return templates.TemplateResponse("index.html", {"request": request, "rates": rates})

# Webpage: Convert currency from form
@app.post("/exchange", response_class=HTMLResponse)
def calculate_exchange(
    request: Request,
    from_currency: str = Form(...),
    to_currency: str = Form(...),
    amount: float = Form(...),
    db: Session = Depends(get_db)
):
    spread = float(os.getenv("SPREAD_PERCENT", 1.5))
    rate_data = crud.get_latest_rate(db, from_currency, to_currency)
    if not rate_data:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "rates": crud.get_all_latest_rates(db),
            "error": "Rate not found in DB"
        })

    fee = (rate_data.rate * spread / 100) * amount
    total = amount * rate_data.rate - fee
    result = schemas.ExchangeOutput(rate=rate_data.rate, result=total, fee=fee)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "rates": crud.get_all_latest_rates(db),
        "result": result
    })

