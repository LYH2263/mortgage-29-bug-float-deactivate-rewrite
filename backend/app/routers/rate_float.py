from fastapi import APIRouter, HTTPException
from app.modules.rate_float import DuplicateEffectivePeriodError, RateFloatError
from app.schemas.rate_float import RateEventCreate, RateEventUpdate
from app.services.mortgage_service import MortgageService, RateFloatConflict

router = APIRouter()


def _conflict(exc):
    ids = getattr(exc, "event_ids", None)
    detail = str(exc)
    if ids:
        detail = f"{detail}（冲突事件标识：{', '.join('#' + str(i) for i in ids)}）"
    raise HTTPException(status_code=409, detail=detail)


@router.get("/loans/{loan_id}/rate-events")
def list_events(loan_id: int):
    with MortgageService() as s:
        try:
            return {"items": s.list_rate_events(loan_id)}
        except LookupError as e:
            raise HTTPException(404, str(e))


@router.post("/loans/{loan_id}/rate-events", status_code=201)
def create_event(loan_id: int, body: RateEventCreate):
    with MortgageService() as s:
        try:
            return s.create_rate_event(loan_id, body.effective_period, body.new_annual_rate, body.note)
        except LookupError as e:
            raise HTTPException(404, str(e))
        except RateFloatConflict as e:
            _conflict(e)
        except RateFloatError as e:
            raise HTTPException(400, str(e))


@router.put("/rate-events/{event_id}")
def update_event(event_id: int, body: RateEventUpdate):
    with MortgageService() as s:
        try:
            return s.update_rate_event(event_id, body.effective_period, body.new_annual_rate, body.note)
        except LookupError as e:
            raise HTTPException(404, str(e))
        except DuplicateEffectivePeriodError as e:
            _conflict(e)
        except RateFloatError as e:
            raise HTTPException(400, str(e))


@router.post("/rate-events/{event_id}/disable")
def disable_event(event_id: int):
    with MortgageService() as s:
        try:
            return s.disable_rate_event(event_id)
        except LookupError as e:
            raise HTTPException(404, str(e))
