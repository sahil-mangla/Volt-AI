
from pydantic import BaseModel, Field
from typing import List, Optional

class CycleData(BaseModel):
    """
    Represents time-series data for a single battery cycle.
    """
    battery_id: str
    cycle_id: int
    time: List[float] = Field(..., description="Time stamps in seconds")
    voltage: List[float] = Field(..., description="Voltage readings")
    current: List[float] = Field(..., description="Current readings")
    temperature: List[float] = Field(..., description="Temperature readings")

class PredictionResponse(BaseModel):
    """
    Response model for prediction endpoint.
    """
    battery_id: str
    cycle: int
    health_score: float
    rul_cycles: float
    soh: float
    status: str
    is_critical: bool
    recommendation: str
