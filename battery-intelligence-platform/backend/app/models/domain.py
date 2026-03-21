from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database.session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="viewer")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Battery(Base):
    __tablename__ = "batteries"

    id = Column(String(50), primary_key=True, index=True)
    model_type = Column(String(100))
    capacity = Column(Float, nullable=False)
    status = Column(String(50), default="HEALTHY")
    installation_date = Column(DateTime(timezone=True), server_default=func.now())

    predictions = relationship("Prediction", back_populates="battery", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="battery", cascade="all, delete-orphan")
    maintenance_orders = relationship("MaintenanceOrder", back_populates="battery")

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    battery_id = Column(String(50), ForeignKey("batteries.id"), nullable=False)
    cycle = Column(Integer, nullable=False)
    health_score = Column(Float, nullable=False)
    rul_cycles = Column(Float, nullable=False)
    failure_risk = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    battery = relationship("Battery", back_populates="predictions")

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    battery_id = Column(String(50), ForeignKey("batteries.id"), nullable=False)
    severity = Column(String(50), nullable=False) # CRITICAL, WARNING
    message = Column(Text, nullable=False)
    is_resolved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    battery = relationship("Battery", back_populates="alerts")

class MaintenanceOrder(Base):
    __tablename__ = "maintenance_orders"

    id = Column(Integer, primary_key=True, index=True)
    battery_id = Column(String(50), ForeignKey("batteries.id"), nullable=False)
    priority = Column(String(50), nullable=False)
    notes = Column(Text)
    status = Column(String(50), default="OPEN") # OPEN, IN_PROGRESS, RESOLVED
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    battery = relationship("Battery", back_populates="maintenance_orders")

class BatterySummary(Base):
    __tablename__ = "battery_summary"

    battery_id = Column(String(50), ForeignKey("batteries.id"), primary_key=True, index=True)
    avg_health = Column(Float, nullable=False)
    max_cycles = Column(Integer, nullable=False)
    failure_risk = Column(Float, default=0.0)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

