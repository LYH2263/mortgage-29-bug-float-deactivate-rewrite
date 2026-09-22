from fastapi import APIRouter
from app.routers import dashboard, history, loans, rate_float, schedule, settings
api = APIRouter(prefix="/api")
for r in (dashboard, loans, schedule, history, settings, rate_float): api.include_router(r.router)
