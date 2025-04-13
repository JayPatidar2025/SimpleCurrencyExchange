from apscheduler.schedulers.background import BackgroundScheduler
from .crud import store_rate
from .database import SessionLocal
import httpx, os
from dotenv import load_dotenv

load_dotenv()
FIXER_API_KEY = os.getenv("FIXER_API_KEY")

def fetch_and_store_rates():
    db = SessionLocal()
    url = f"https://data.fixer.io/api/latest?access_key={FIXER_API_KEY}"
    res = httpx.get(url)
    data = res.json()
    base = data["base"]
    rates = data["rates"]
    for target, rate in rates.items():
        store_rate(db, base, target, rate)

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_and_store_rates, "interval", hours=1)
    scheduler.start()

