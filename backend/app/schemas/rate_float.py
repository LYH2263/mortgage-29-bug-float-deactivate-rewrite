from pydantic import BaseModel, Field


class RateEventCreate(BaseModel):
    effective_period: int = Field(gt=1)
    new_annual_rate: float = Field(ge=0)
    note: str = ""


class RateEventUpdate(BaseModel):
    effective_period: int = Field(gt=1)
    new_annual_rate: float = Field(ge=0)
    note: str = ""
