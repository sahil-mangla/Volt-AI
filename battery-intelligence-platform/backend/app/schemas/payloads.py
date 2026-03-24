from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class CycleData(BaseModel):
    battery_id: str
    cycle_id: int
    time: List[float] = Field(..., description="Time stamps in seconds")
    voltage: List[float] = Field(..., description="Voltage readings")
    current: List[float] = Field(..., description="Current readings")
    temperature: List[float] = Field(..., description="Temperature readings")

class PredictionResponse(BaseModel):
    battery_id: str
    cycle: int
    health_score: float
    rul_cycles: float
    failure_risk: float
    status: str
    is_critical: bool
    recommendation: str

class BatterySummary(BaseModel):
    id: str
    health: float
    rul: float
    status: str
    model_type: Optional[str] = None

class MaintenanceRequest(BaseModel):
    battery_id: str
    priority: str
    notes: Optional[str] = None

class MaintenanceResponse(BaseModel):
    id: int
    battery_id: str
    priority: str
    status: str
    message: str

class AlertResponse(BaseModel):
    id: int
    battery_id: str
    severity: str
    message: str
    is_resolved: bool
    created_at: datetime

class ModelSelectRequest(BaseModel):
    model_name: str
